Self-Healing Infrastructure
===========================

This daemon utilizes the Sensu monitoring & SaltStack framework. When a system
fails its monitoring health check, a Salt state (remedy) will be run against
the system. If the issue cannot be resolved, an operator will be contacted.

Starting meditation:-

```bash
./meditation.py -c meditation.ini -s remedy -p 2
```

* -c specifies where the configuration file lives
* -s specifies where the Salt states exist
* -p specifies how many worker processes you would like to start

NOTE: The `-s` option will use the file_roots as a prefix, so the
default for command executed above will be `/srv/salt/remedy`
