import argparse
from addbiomechanics.auth import AuthContext


class AbstractCommand:
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        pass

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        pass

    def run_local(self, args: argparse.Namespace) -> bool:
        return False
