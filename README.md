Self-Healing Infrastructure
===========================

This daemon utilizes the Sensu monitoring & SaltStack framework. When a system
fails its monitoring health check, a Salt state (remedy) will be run against
the system. If the issue cannot be resolved, an operator will be contacted.






```TODO```
* Integrate Celery / Damonize (Need to query the Sensu API)
* Write unit tests
