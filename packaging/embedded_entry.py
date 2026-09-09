from multiprocessing import freeze_support

from lte_sim.embedded_app import main


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())
