---
id: task_readme_generation
name: README Generation
category: developer
grading_type: llm_judge
timeout_seconds: 180
workspace_files:
  - path: "src/index.ts"
    content: |
      import express from 'express';
      import { config } from './config';
      import { authRouter } from './routes/auth';
      import { tasksRouter } from './routes/tasks';
      import { webhookRouter } from './routes/webhooks';
      import { connectDb } from './db';
      import { logger } from './utils/logger';

      const app = express();

      app.use(express.json());
      app.use('/api/auth', authRouter);
      app.use('/api/tasks', tasksRouter);
      app.use('/api/webhooks', webhookRouter);

      app.get('/health', (_req, res) => res.json({ status: 'ok' }));

      async function main() {
        await connectDb();
        app.listen(config.port, () => {
          logger.info(`TaskFlow API listening on port ${config.port}`);
        });
      }

      main().catch((err) => {
        logger.error('Failed to start server', err);
        process.exit(1);
      });
  - path: "src/config.ts"
    content: |
      import dotenv from 'dotenv';
      dotenv.config();

      export const config = {
        port: parseInt(process.env.PORT || '3000', 10),
        databaseUrl: process.env.DATABASE_URL || 'postgresql://localhost:5432/taskflow',
        jwtSecret: process.env.JWT_SECRET || 'change-me',
        redisUrl: process.env.REDIS_URL || 'redis://localhost:6379',
        webhookSecret: process.env.WEBHOOK_SECRET || '',
      };
  - path: "src/routes/auth.ts"
    content: |
      import { Router } from 'express';
      import bcrypt from 'bcrypt';
      import jwt from 'jsonwebtoken';
      import { db } from '../db';
      import { config } from '../config';

      export const authRouter = Router();

      authRouter.post('/register', async (req, res) => {
        const { email, password, name } = req.body;
        const hash = await bcrypt.hash(password, 12);
        const user = await db.user.create({ data: { email, password: hash, name } });
        res.status(201).json({ id: user.id, email: user.email });
      });

      authRouter.post('/login', async (req, res) => {
        const { email, password } = req.body;
        const user = await db.user.findUnique({ where: { email } });
        if (!user || !(await bcrypt.compare(password, user.password))) {
          return res.status(401).json({ error: 'Invalid credentials' });
        }
        const token = jwt.sign({ sub: user.id }, config.jwtSecret, { expiresIn: '7d' });
        res.json({ token });
      });
  - path: "src/routes/tasks.ts"
    content: |
      import { Router } from 'express';
      import { db } from '../db';
      import { authenticate } from '../middleware/auth';

      export const tasksRouter = Router();
      tasksRouter.use(authenticate);

      tasksRouter.get('/', async (req, res) => {
        const tasks = await db.task.findMany({ where: { userId: req.userId } });
        res.json(tasks);
      });

      tasksRouter.post('/', async (req, res) => {
        const { title, description, dueDate } = req.body;
        const task = await db.task.create({
          data: { title, description, dueDate: new Date(dueDate), userId: req.userId },
        });
        res.status(201).json(task);
      });

      tasksRouter.patch('/:id', async (req, res) => {
        const task = await db.task.update({
          where: { id: req.params.id, userId: req.userId },
          data: req.body,
        });
        res.json(task);
      });

      tasksRouter.delete('/:id', async (req, res) => {
        await db.task.delete({ where: { id: req.params.id, userId: req.userId } });
        res.status(204).send();
      });
  - path: "src/routes/webhooks.ts"
    content: |
      import { Router } from 'express';
      import crypto from 'crypto';
      import { config } from '../config';
      import { db } from '../db';

      export const webhookRouter = Router();

      webhookRouter.post('/task-complete', async (req, res) => {
        const signature = req.headers['x-webhook-signature'] as string;
        const payload = JSON.stringify(req.body);
        const expected = crypto.createHmac('sha256', config.webhookSecret).update(payload).digest('hex');
        if (signature !== expected) {
          return res.status(403).json({ error: 'Invalid signature' });
        }
        const { taskId, completedAt } = req.body;
        await db.task.update({ where: { id: taskId }, data: { completedAt: new Date(completedAt), status: 'done' } });
        res.json({ ok: true });
      });
  - path: "package.json"
    content: |
      {
        "name": "taskflow-api",
        "version": "1.2.0",
        "description": "Task management REST API",
        "main": "dist/index.js",
        "scripts": {
          "dev": "ts-node-dev --respawn src/index.ts",
          "build": "tsc",
          "start": "node dist/index.js",
          "test": "jest",
          "lint": "eslint src/",
          "db:migrate": "prisma migrate dev",
          "db:seed": "ts-node prisma/seed.ts"
        },
        "dependencies": {
          "express": "^4.18.2",
          "bcrypt": "^5.1.1",
          "jsonwebtoken": "^9.0.2",
          "ioredis": "^5.3.2",
          "dotenv": "^16.3.1",
          "@prisma/client": "^5.7.0"
        },
        "devDependencies": {
          "typescript": "^5.3.3",
          "ts-node-dev": "^2.0.0",
          "jest": "^29.7.0",
          "@types/express": "^4.17.21",
          "eslint": "^8.56.0",
          "prisma": "^5.7.0"
        },
        "license": "MIT"
      }
  - path: "prisma/schema.prisma"
    content: |
      generator client {
        provider = "prisma-client-js"
      }

      datasource db {
        provider = "postgresql"
        url      = env("DATABASE_URL")
      }

      model User {
        id        String   @id @default(uuid())
        email     String   @unique
        password  String
        name      String
        tasks     Task[]
        createdAt DateTime @default(now())
      }

      model Task {
        id          String    @id @default(uuid())
        title       String
        description String?
        status      String    @default("pending")
        dueDate     DateTime?
        completedAt DateTime?
        user        User      @relation(fields: [userId], references: [id])
        userId      String
        createdAt   DateTime  @default(now())
        updatedAt   DateTime  @updatedAt
      }
  - path: ".env.example"
    content: |
      PORT=3000
      DATABASE_URL=postgresql://user:password@localhost:5432/taskflow
      JWT_SECRET=your-secret-key
      REDIS_URL=redis://localhost:6379
      WEBHOOK_SECRET=your-webhook-secret
---

# README Generation

## Prompt

Examine the source code in this workspace — it is a small TypeScript REST API project. Generate a comprehensive `README.md` for the project.

The README should include:

1. **Project title and description** — what the project does.
2. **Tech stack** — languages, frameworks, and key libraries used.
3. **Getting started** — prerequisites, installation steps, and how to run the project locally (including database setup).
4. **Environment variables** — a table or list explaining each variable from `.env.example`.
5. **API endpoints** — document the available routes with HTTP methods and brief descriptions.
6. **Available scripts** — explain what each npm script does.
7. **License** — based on what is in `package.json`.

Save the output as `README.md` in the workspace root.

## Expected Behavior

The agent should read the source files to understand the project structure, then generate a well-organized README that accurately reflects the codebase.

Key details the agent should discover and include:

- The project is called "TaskFlow API" (from package.json name/description and the logger output).
- Tech stack: TypeScript, Express, Prisma (PostgreSQL), Redis, JWT auth, bcrypt.
- Routes: `/api/auth` (register, login), `/api/tasks` (CRUD), `/api/webhooks` (task-complete), `/health`.
- Environment variables: PORT, DATABASE_URL, JWT_SECRET, REDIS_URL, WEBHOOK_SECRET.
- Scripts: dev, build, start, test, lint, db:migrate, db:seed.
- License: MIT.

The README should be well-structured with clear headings, code blocks for commands, and accurate information derived from the actual source code (not hallucinated features).

## Grading Criteria

- [ ] File `README.md` is created
- [ ] Includes project name and accurate description
- [ ] Lists the correct tech stack
- [ ] Provides getting-started/installation instructions
- [ ] Documents environment variables from `.env.example`
- [ ] Documents API endpoints with HTTP methods
- [ ] Explains available npm scripts
- [ ] Mentions the license
- [ ] Content is accurate and derived from the actual source code

## LLM Judge Rubric

### Criterion 1: Accuracy and Faithfulness (Weight: 30%)

**Score 1.0**: All information in the README is derived from the actual source code. Tech stack, endpoints, env vars, and scripts are correct with no hallucinated features or libraries.

**Score 0.75**: Mostly accurate with one minor inaccuracy or assumed detail not in the source.

**Score 0.5**: Generally correct but includes notable inaccuracies or fabricated details.

**Score 0.25**: Multiple significant inaccuracies or hallucinated features.

**Score 0.0**: Mostly fabricated content not reflecting the actual codebase.

### Criterion 2: Completeness (Weight: 25%)

**Score 1.0**: Covers all required sections: title/description, tech stack, getting started, env vars, API endpoints, scripts, and license. No major section missing.

**Score 0.75**: Covers most sections with one minor omission.

**Score 0.5**: Missing two or more sections or several sections are superficial.

**Score 0.25**: Minimal coverage; most required sections missing.

**Score 0.0**: No meaningful README content.

### Criterion 3: API Documentation Quality (Weight: 20%)

**Score 1.0**: All routes are documented with HTTP methods, paths, and brief descriptions. Auth routes (register, login), task CRUD routes, webhook endpoint, and health check are all covered.

**Score 0.75**: Most routes documented with minor gaps (e.g., missing health check or one CRUD operation).

**Score 0.5**: Partial route documentation; several endpoints missing or methods incorrect.

**Score 0.25**: Minimal API documentation.

**Score 0.0**: No API documentation.

### Criterion 4: Structure and Readability (Weight: 15%)

**Score 1.0**: Well-organized with clear headings, consistent formatting, proper use of code blocks for commands and env vars, and easy to follow for a new developer.

**Score 0.75**: Good structure with minor formatting inconsistencies.

**Score 0.5**: Readable but poorly organized or inconsistent formatting.

**Score 0.25**: Hard to follow or poorly structured.

**Score 0.0**: Unreadable or unstructured.

### Criterion 5: Getting Started Quality (Weight: 10%)

**Score 1.0**: Clear step-by-step setup instructions including prerequisites (Node.js, PostgreSQL, Redis), installing dependencies, setting up env vars, running migrations, and starting the server.

**Score 0.75**: Good setup instructions with one minor gap.

**Score 0.5**: Basic instructions but missing key steps (e.g., database migration or Redis).

**Score 0.25**: Minimal or unclear setup instructions.

**Score 0.0**: No setup instructions.

## Additional Notes

- This task evaluates whether the agent can analyze a codebase and produce accurate, well-structured documentation.
- The workspace contains enough files to fully document the project without guessing — strong answers will reference actual code patterns (e.g., Prisma for ORM, bcrypt for password hashing) rather than making generic assumptions.
- The agent should not fabricate endpoints, features, or dependencies that do not exist in the source files.
