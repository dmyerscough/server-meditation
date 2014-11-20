# Self-Healing Infrastructure
This daemon utilizes the Sensu monitoring and SaltStack framework. When a system
fails its monitoring health check, a Salt state (remedy) will be run against
the system. If the issue cannot be resolved, an operator will be contacted.

Starting meditation:-

```bash
./meditation.py -c meditation.ini -s remedy -p 2
```

* `-c` specifies where the configuration file lives
* `-s` specifies where the Salt states exist
* `-p` specifies how many worker processes you would like to start

NOTE 
====
The `-s` option will use the `file_roots` as a prefix, so the
`-s` option will be fully expanded to `/srv/salt/remedy`.

### Configure Sensu
When configuring Sensu monitoring, you need to make sure the `check_name`
matches the same name as the Salt remediation state e.g.

```json
{
  "checks": {
    "cron_check": {
      "handlers": ["default"],
      "command": "/etc/sensu/plugins/check-procs.rb -p crond -C 1 ",
      "interval": 60,
      "subscribers": [ "webservers" ]
    }
  }
}
```

The Salt remediation state would be called: `cron_check.sls` and would contain
something like the following lines:-

```yaml
crond:
  service:
    - name: crond
    - running
```
