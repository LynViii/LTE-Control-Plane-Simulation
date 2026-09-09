from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ATResult:
    ok: bool
    response: str
    action: str


class ATParser:
    """Small AT-command parser for the AP→Modem control channel.

    The parser intentionally supports the three forms students most often need
    to distinguish when reading modem specifications:
      * execute: ``AT`` / ``AT+CSQ``
      * query:   ``AT+CFUN?``
      * test:    ``AT+CFUN=?``
      * set:     ``AT+CFUN=1`` / ``AT+CFUN=0``

    Only the subset needed by this Attach simulator is implemented. This is an
    interface simulator rather than a full 3GPP TS 27.007 implementation.
    """

    MAX_COMMAND_CHARS = 256

    @staticmethod
    def parse(raw_command: str, state: dict) -> ATResult:
        raw = str(raw_command or "")
        if not raw.strip():
            return ATResult(False, "ERROR: EMPTY_COMMAND", "none")
        if len(raw) > ATParser.MAX_COMMAND_CHARS:
            return ATResult(False, "ERROR: COMMAND_TOO_LONG", "invalid")
        if "\r" in raw.strip("\r\n") or "\n" in raw.strip("\r\n"):
            return ATResult(False, "ERROR: MULTI_COMMAND_NOT_ALLOWED", "invalid")

        command = raw.strip().upper()
        if not command.startswith("AT"):
            return ATResult(False, "ERROR: MISSING_AT_PREFIX", "invalid")

        if command == "AT":
            return ATResult(True, "OK", "ping")
        if command == "AT+HELP":
            return ATResult(
                True,
                "+HELP: AT,CFUN,CGATT,CREG,CSQ,COPS,CELL,SEC,TASK,SIMSCENARIO,RESET\r\nOK",
                "help",
            )

        # CFUN: query / test / set forms.
        if command == "AT+CFUN?":
            return ATResult(True, f"+CFUN: {state['modem']['cfun']}\r\nOK", "queryCfun")
        if command == "AT+CFUN=?":
            return ATResult(True, "+CFUN: (0,1)\r\nOK", "testCfun")
        if command == "AT+CFUN=0":
            return ATResult(True, "OK", "cfun0")
        if command == "AT+CFUN=1":
            return ATResult(True, "OK", "attach")
        if command.startswith("AT+CFUN="):
            return ATResult(False, "ERROR: INVALID_CFUN_VALUE", "invalid")

        # Registration and status commands.
        if command == "AT+CGATT?":
            attached = 1 if state["modem"]["attachStatus"] == "ATTACHED" else 0
            return ATResult(True, f"+CGATT: {attached}\r\nOK", "queryAttach")
        if command == "AT+CGATT=?":
            return ATResult(True, "+CGATT: (0,1)\r\nOK", "testAttach")
        if command == "AT+CGATT=1":
            return ATResult(True, "OK", "attach")
        if command == "AT+CGATT=0":
            return ATResult(True, "OK", "cfun0")
        if command.startswith("AT+CGATT="):
            return ATResult(False, "+CME ERROR: 50", "invalid")
        if command == "AT+CREG?":
            status = state["modem"]["attachStatus"]
            reg = 1 if status == "ATTACHED" else (2 if status in {"SEARCHING", "CAMPED", "ATTACHING"} else 0)
            return ATResult(True, f"+CREG: 0,{reg}\r\nOK", "queryRegister")
        if command == "AT+CREG=?":
            return ATResult(True, "+CREG: (0-2)\r\nOK", "testRegister")
        if command == "AT+CSQ":
            return ATResult(True, "+CSQ: 23,99\r\nOK", "querySignal")
        if command == "AT+CSQ=?":
            return ATResult(True, "+CSQ: (0-31,99),(0-7,99)\r\nOK", "testSignal")
        if command == "AT+COPS?":
            plmn = str(state.get("enb", {}).get("plmn", "460-01")).replace("-", "")
            return ATResult(True, f'+COPS: 0,2,"{plmn}",7\r\nOK', "queryOperator")
        if command == "AT+COPS=?":
            return ATResult(True, '+COPS: (2,"SIM-LTE","SIM","46001",7)\r\nOK', "testOperator")
        if command.startswith("AT+COPS="):
            return ATResult(False, "+CME ERROR: 3", "invalid")

        # Simulator-specific diagnostics used to observe the Attach result.
        if command == "AT+CELL?":
            cell = state["modem"].get("cell")
            if not cell:
                return ATResult(True, "+CELL: NOT_CAMPED\r\nOK", "queryCell")
            return ATResult(
                True,
                f"+CELL: {cell['cellId']},{cell['plmn']},{cell['tac']},{cell['bandwidth']}\r\nOK",
                "queryCell",
            )
        if command == "AT+CELL=?":
            return ATResult(True, "+CELL: (query only)\r\nOK", "testCell")
        if command == "AT+SEC?":
            sec = state.get("security", {})
            active = 1 if sec.get("active") else 0
            return ATResult(
                True,
                f'+SEC: {active},"{sec.get("nasCipher", "--")}","{sec.get("nasIntegrity", "--")}","{sec.get("keyId", "--")}"\r\nOK',
                "querySecurity",
            )
        if command == "AT+SEC=?":
            return ATResult(True, "+SEC: (query only)\r\nOK", "testSecurity")
        if command == "AT+TASK?":
            runtime = state.get("taskRuntime", {})
            fields = [f'{name}:{runtime.get(name, {}).get("status", "IDLE")}' for name in ("NAS", "RRC", "L2", "L1")]
            return ATResult(True, "+TASK: " + ",".join(fields) + "\r\nOK", "queryTasks")
        if command == "AT+TASK=?":
            return ATResult(True, "+TASK: (query only)\r\nOK", "testTasks")
        if command == "AT+SIMSCENARIO?":
            scenario = state.get("scenario", {}).get("id", "NORMAL")
            return ATResult(True, f"+SIMSCENARIO: {scenario}\r\nOK", "queryScenario")
        if command == "AT+SIMSCENARIO=?":
            return ATResult(True, "+SIMSCENARIO: (query only)\r\nOK", "testScenario")
        if command == "AT+RESET":
            return ATResult(True, "OK", "reset")

        return ATResult(False, "ERROR: UNSUPPORTED_COMMAND", "unsupported")
