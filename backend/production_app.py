"""Explicit recovery launcher. Importing this module never loads app/.env or SQL."""
import argparse
import sys

from production_guard import StartupGuardError, create_guarded_engine, load_profile, validate_startup


def create_production_app(profile_path):
    profile = load_profile(profile_path)
    engine = create_guarded_engine(profile)
    try:
        validate_startup(engine, profile)
        # Composition has no global application: no default root engine is created.
        from application_factory import create_app
        return create_app(profile.settings(), engine=engine,
                          startup_validator=lambda current, settings: validate_startup(current, profile))
    except Exception:
        engine.dispose()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Opt-in guarded recovery backend; operator approval required for production")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    engine = None
    try:
        profile = load_profile(args.profile)
        if args.check_only:
            engine = create_guarded_engine(profile)
            validate_startup(engine, profile)
            print("PRODUCTION_STARTUP_GUARD_PASS")
            return 0
        if not args.host:
            parser.error("--host must explicitly preserve the approved HTTP binding")
        import uvicorn
        # Validation occurs before uvicorn receives the app and again during lifespan.
        app = create_production_app(args.profile)
        uvicorn.run(app, host=args.host, port=args.port, proxy_headers=False,
                    lifespan="on", reload=False, log_level="info")
        return 0
    except Exception:
        # Connector exceptions/tracebacks can contain sensitive connection details.
        print("PRODUCTION_STARTUP_GUARD_REJECTED", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
