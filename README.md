# atrio
## Trio communication through telnet
The telnet connection is to be shared with Motion Perfect, so it needs to be closed for the scripts in this folder to work.

The trio script allows to send command to a trio motion controller and manage the programs in the controller.

## Command line usage examples

To list the files in the controller:
```
$ atrio --ip 192.168.0.100 ls
PROGRAM_1.BAS
AUTORUN_PROG.BAS (10)
MC_CONFIG.MCC
```

To run a command as if in the command line:
```
$ atrio --ip 192.168.0.100 cmd "?VERSION"
2.0305
```

## The atrio python library provide full control over a controller
