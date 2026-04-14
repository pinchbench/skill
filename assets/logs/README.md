# Sample Log Files for PinchBench

This directory contains diverse sample log files for testing log parsing and analysis tasks in PinchBench.

## Files

### 1. apache_error.log
- **Type:** Web server error logs
- **Source:** [Loghub Apache dataset](https://github.com/logpai/loghub/tree/master/Apache)
- **Size:** ~96KB (1,000 lines)
- **Format:** Apache error log format
  ```
  [Thu Jun 09 06:07:04 2005] [notice] LDAP: Built with OpenLDAP LDAP SDK
  ```
- **Description:** Error and notice logs from an Apache web server including module initialization messages, authentication events, and server status notifications.

### 2. linux_syslog.log
- **Type:** System logs (syslog)
- **Source:** [Loghub Linux dataset](https://github.com/logpai/loghub/tree/master/Linux)
- **Size:** ~510KB (5,000 lines)
- **Format:** Standard Linux syslog format
  ```
  Jun  9 06:06:20 combo syslogd 1.4.1: restart.
  Jun  9 06:06:20 combo kernel: Linux version 2.6.5-1.358
  ```
- **Description:** System logs from a Linux server including kernel messages, daemon startups, cron jobs, and system events.

### 3. hdfs_datanode.log
- **Type:** Distributed file system logs
- **Source:** [Loghub HDFS dataset](https://github.com/logpai/loghub/tree/master/HDFS)
- **Size:** ~284KB (2,000 lines)
- **Format:** Hadoop DataNode log format
  ```
  081109 203518 143 INFO dfs.DataNode$DataXceiver: Receiving block blk_-1608999687919862906
  ```
- **Description:** HDFS (Hadoop Distributed File System) DataNode logs showing block operations, data transfers, and NameSystem interactions.

### 4. openssh_auth.log
- **Type:** Authentication/security logs
- **Source:** [Loghub OpenSSH dataset](https://github.com/logpai/loghub/tree/master/OpenSSH)
- **Size:** ~165KB (1,500 lines)
- **Format:** OpenSSH auth log format
  ```
  Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user webmaster from 173.234.31.186
  Dec 10 06:55:46 LabSZ sshd[24200]: pam_unix(sshd:auth): authentication failure
  ```
- **Description:** SSH authentication logs including failed login attempts, invalid user attempts, and PAM authentication events.

### 5. hadoop_mapreduce.log
- **Type:** Application logs (MapReduce)
- **Source:** [Loghub Hadoop dataset](https://github.com/logpai/loghub/tree/master/Hadoop)
- **Size:** ~235KB (1,282 lines)
- **Format:** Hadoop MapReduce application log format
  ```
  2015-10-17 15:37:56,547 INFO [main] org.apache.hadoop.mapreduce.v2.app.MRAppMaster: Created MRAppMaster
  ```
- **Description:** Hadoop MapReduce job execution logs showing application master initialization, container management, and job lifecycle events.

### 6. nginx_access_json.log
- **Type:** Web server access logs (JSON format)
- **Source:** [Elastic Examples - NGINX JSON logs](https://github.com/elastic/examples/tree/master/Common%20Data%20Formats/nginx_json_logs)
- **Size:** ~228KB (1,000 lines)
- **Format:** JSON structured logs
  ```json
  {"time": "17/May/2015:08:05:32 +0000", "remote_ip": "93.180.71.3", "remote_user": "-",
   "request": "GET /downloads/product_1 HTTP/1.1", "response": 304, "bytes": 0,
   "referrer": "-", "agent": "Debian APT-HTTP/1.3"}
  ```
- **Description:** NGINX access logs in JSON format showing HTTP requests with response codes, bytes transferred, user agents, and timestamps. Useful for testing JSON log parsing.

## Usage Notes

- All log files are samples extracted from larger datasets to keep file sizes manageable (all under 500KB)
- These files represent diverse log formats: plain text, structured, and JSON
- Use cases include: log parsing, anomaly detection, pattern matching, and format recognition tasks

## Attribution

- Loghub datasets: Zhu et al. "Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics", IEEE ISSRE 2023.
- Elastic Examples: https://github.com/elastic/examples

## License

These sample files are provided for research and testing purposes. Please refer to the original sources for license details:
- Loghub: https://github.com/logpai/loghub
- Elastic Examples: https://github.com/elastic/examples
