# backdorOS

backdorOS is an in-memory OS written in Python 2.7 with a built-in in-memory filesystem, hooks for open() calls and imports, Python REPL etc.

## Install

```
$ git clone https://github.com/SafeBreach-Labs/backdoros
$ cd backdoros
$ ./backdoros.py &
$ telnet localhost 31337
```

OR

```
$ curl -fsSL http://URL/backdoros.py | python &
$ telnet localhost 31337

```

backdorOS was released as part of the [BackdorOS: The In-memory OS for Red Teams](https://texascybersummitii2019.sched.com/event/Tqsp/fr-2016-red-team-backdoros-in-memory?iframe=no&w=100%25&sidebar=no&bg=dark) talk given at Texas Cyber Summit 2019 conference by Itzik Kotler from [SafeBreach Labs](http://www.safebreach.com).

## Version
0.1.0

## License
BSD 3-Clause
