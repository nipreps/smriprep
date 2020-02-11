from .cli.run import main

if __name__ == '__main__':
    import sys
    # `python -m smriprep` typically displays the command as __main__.py
    if '__main__.py' in sys.argv[0]:
        sys.argv[0] = '%s -m smriprep' % sys.executable
    main()
