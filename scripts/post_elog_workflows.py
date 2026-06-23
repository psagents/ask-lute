"""Script to register LUTE workflow definitions in the LCLS eLog.

Run this after install_lute.py has set up the workspace and DAG files.
"""

__author__ = "Gabriel Dorlhiac"

import argparse
import logging
import os
import subprocess
import sys
from typing import Any, Dict, List, Optional

import requests
from krtc import KerberosTicket  # type: ignore


logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# Trigger map for known workflow names.
# Workflows not listed here default to END_OF_RUN.
WORKFLOW_TRIGGERS: Dict[str, Dict[str, str]] = {
    # Downstream SMD analysis — trigger when SmallData run param is set to "done"
    "smd_xss": {
        "trigger": "RUN_PARAM_IS_VALUE",
        "run_param_name": "SmallData",
        "run_param_value": "done",
    },
    "smd_xas": {
        "trigger": "RUN_PARAM_IS_VALUE",
        "run_param_name": "SmallData",
        "run_param_value": "done",
    },
    "smd_xes": {
        "trigger": "RUN_PARAM_IS_VALUE",
        "run_param_name": "SmallData",
        "run_param_value": "done",
    },
    "smd_summaries": {
        "trigger": "RUN_PARAM_IS_VALUE",
        "run_param_name": "SmallData",
        "run_param_value": "done",
    },
    # Manual trigger — geometry optimization is intentionally run by the user
    "bayfai": {"trigger": "MANUAL"},
}

DEFAULT_TRIGGER: Dict[str, str] = {"trigger": "END_OF_RUN"}


def check_kerberos_ticket() -> bool:
    """Return True if a valid, non-expired Kerberos ticket exists at $HOME/krb5cc.ticket.

    Uses klist to inspect the credential cache without requiring any user interaction.
    """
    ticket_path: str = f"FILE:{os.environ['HOME']}/krb5cc.ticket"
    result: subprocess.CompletedProcess = subprocess.run(
        ["klist", "-c", ticket_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.returncode == 0


def get_lute_paths(
    experiment: str,
    version: str,
    fresh_install: bool,
    directory: str,
) -> Dict[str, str]:
    """Derive LUTE executable and config paths without performing any setup.

    Mirrors the path logic in install_lute.py so both scripts stay consistent.

    Args:
        experiment (str): LCLS experiment name (e.g. mfxl1013621).
        version (str): LUTE version tag or 'dev'.
        fresh_install (bool): Whether a fresh install was used during setup.
        directory (str): Optional subdirectory under results/ used during install.

    Returns:
        Dict[str, str]: Keys: lute_path, lute_output_dir, config_path,
            arp_executable, launch_executable.
    """
    hutch: str = experiment[:3]
    results_dir: str = f"/sdf/data/lcls/ds/{hutch}/{experiment}/results"
    if directory:
        results_dir = f"{results_dir}/{directory}"

    lute_output_dir: str = f"{results_dir}/lute_output"
    config_path: str = f"{lute_output_dir}/{hutch}_lute.yaml"

    lute_path: str
    if fresh_install:
        lute_path = f"{results_dir}/lute"
        arp_executable: str = f"{lute_path}/install/bin/submit_launch_slurm.sh"
        launch_executable: str = f"{lute_path}/install/bin/launch_slurm"
    else:
        lute_path = f"/sdf/group/lcls/ds/tools/lute/{version}/lute"
        arp_executable = f"{lute_path}/install/bin/submit_launch_slurm.sh"
        launch_executable = f"{lute_path}/install/bin/launch_slurm"

    return {
        "lute_path": lute_path,
        "lute_output_dir": lute_output_dir,
        "config_path": config_path,
        "arp_executable": arp_executable,
        "launch_executable": launch_executable,
    }


def build_param_string(
    launch_executable: str,
    config_path: str,
    workflow_path: str,
    partition: str,
    account: str,
    debug: bool = False,
    test: bool = False,
) -> str:
    """Build the parameter string stored in the eLog workflow definition.

    Args:
        launch_executable (str): Path to the launch_slurm binary.
        config_path (str): Path to the LUTE YAML config file.
        workflow_path (str): Path to the workflow DAG file.
        partition (str): SLURM partition (e.g. milano).
        account (str): SLURM account (e.g. lcls:mfxl1013621).
        debug (bool): Pass --debug to launch_slurm.
        test (bool): Pass --test to use the test Airflow instance.

    Returns:
        str: Formatted parameter string for the eLog workflow entry.
    """
    param_string: str = (
        f"{launch_executable} -c {config_path} -W {workflow_path} "
        f"--partition={partition} --account={account}"
    )
    if debug:
        param_string = f"{param_string} --debug"
    if test:
        param_string = f"{param_string} --test"
    return param_string


def post_workflow_to_elog(experiment: str, workflow: Dict[str, Any]) -> None:
    """POST a single workflow definition to the LCLS eLog.

    Requires a valid Kerberos ticket at $HOME/krb5cc.ticket and
    KRB5CCNAME set to FILE:$HOME/krb5cc.ticket before calling this function.

    Args:
        experiment (str): LCLS experiment name.
        workflow (Dict[str, Any]): Workflow definition dict with keys:
            name, executable, location, parameters, trigger (and optionally
            run_param_name, run_param_value for RUN_PARAM_IS_VALUE trigger).

    Raises:
        requests.exceptions.HTTPError: If the eLog API returns a non-2xx status.
    """
    krbticket: KerberosTicket = KerberosTicket("HTTP@pswww.slac.stanford.edu")
    krbheaders: dict = krbticket.getAuthHeaders()
    url: str = (
        f"https://pswww.slac.stanford.edu/ws-kerb/lgbk/lgbk/{experiment}/ws"
        "/create_update_workflow_def"
    )
    resp: requests.models.Response = requests.post(
        url=url,
        headers=krbheaders,
        json=workflow,
    )
    resp.raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="post_elog_workflows",
        description=(
            "Register LUTE workflow definitions in the LCLS eLog. "
            "Run this after install_lute.py has set up the workspace and DAG files."
        ),
        epilog="Refer to https://github.com/slac-lcls/lute for more information.",
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Turn on verbose logging."
    )
    parser.add_argument(
        "-e",
        "--experiment",
        type=str,
        required=True,
        help="LCLS experiment name (e.g. mfxl1013621).",
    )
    parser.add_argument(
        "-f",
        "--fresh_install",
        action="store_true",
        help=(
            "Was a fresh LUTE install used? Affects path derivation. "
            "Must match the flag used in install_lute.py."
        ),
    )
    parser.add_argument(
        "-D",
        "--directory",
        type=str,
        default="",
        help="Subdirectory under the experiment results folder used during install.",
    )
    parser.add_argument(
        "-v",
        "--version",
        type=str,
        default="dev",
        help="LUTE version tag or 'dev'. Must match what was used in install_lute.py.",
    )
    parser.add_argument(
        "-W",
        "--workflow",
        type=str,
        nargs="+",
        action="extend",
        help="Workflow name(s) to register. E.g. -W smd smd_xss bayfai.",
    )
    parser.add_argument(
        "--partition",
        type=str,
        default="milano",
        help="SLURM partition used in the workflow parameter string. Default: milano.",
    )
    parser.add_argument(
        "--account",
        type=str,
        default="",
        help="SLURM account. Default: lcls:<experiment>.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use the test Airflow instance.",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    # --- Kerberos check (must happen before any eLog interaction) ---
    if not check_kerberos_ticket():
        logger.error(
            "No valid Kerberos ticket found at $HOME/krb5cc.ticket.\n"
            "Run the following in your terminal, then retry this script:\n\n"
            "  kinit -c FILE:$HOME/krb5cc.ticket <username>@SLAC.STANFORD.EDU\n\n"
            "The FILE: prefix is required so the ticket is written to a file that\n"
            "both this script and the LUTE submission scripts can read."
        )
        sys.exit(1)

    # Set KRB5CCNAME so krtc picks up the correct credential cache file.
    # The FILE: prefix must match exactly what was used with kinit -c.
    os.environ["KRB5CCNAME"] = f"FILE:{os.environ['HOME']}/krb5cc.ticket"
    logger.info("Kerberos ticket validated.")

    account: str = args.account if args.account else f"lcls:{args.experiment}"
    workflow_names: List[str] = args.workflow if args.workflow else ["smd"]

    paths: Dict[str, str] = get_lute_paths(
        experiment=args.experiment,
        version=args.version,
        fresh_install=args.fresh_install,
        directory=args.directory,
    )

    logger.debug(f"Derived paths: {paths}")

    failed: List[str] = []
    for wf_name in workflow_names:
        wf_path: str = f"{paths['lute_output_dir']}/{wf_name}.dag"
        if not os.path.exists(wf_path):
            logger.error(
                f"DAG file not found for workflow '{wf_name}' at: {wf_path}. "
                "Run install_lute.py first, or check the workflow name. Skipping."
            )
            failed.append(wf_name)
            continue

        param_string: str = build_param_string(
            launch_executable=paths["launch_executable"],
            config_path=paths["config_path"],
            workflow_path=wf_path,
            partition=args.partition,
            account=account,
            debug=args.debug,
            test=args.test,
        )

        trigger: Dict[str, str] = WORKFLOW_TRIGGERS.get(wf_name, DEFAULT_TRIGGER)

        workflow: Dict[str, Any] = {
            "name": f"lute_{wf_name}",
            "executable": paths["arp_executable"],
            "location": "S3DF",
            "parameters": param_string,
            **trigger,
        }

        logger.info(
            f"Registering eLog workflow: lute_{wf_name}  "
            f"(trigger: {trigger['trigger']})"
        )
        try:
            post_workflow_to_elog(args.experiment, workflow)
            logger.info(f"Successfully registered: lute_{wf_name}")
        except requests.exceptions.HTTPError as exc:
            logger.error(f"Failed to register lute_{wf_name}: {exc}")
            failed.append(wf_name)

    if failed:
        logger.error(f"The following workflows failed to register: {failed}")
        sys.exit(1)
    else:
        logger.info(
            f"All workflows registered. Verify at:\n"
            f"  https://pswww.slac.stanford.edu/lgbk/lgbk/{args.experiment}/"
            f"  (Workflow Definitions tab)"
        )


if __name__ == "__main__":
    main()
