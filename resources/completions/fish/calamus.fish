# fish completion for calamus
# Install to: /usr/share/fish/vendor_completions.d/calamus.fish

complete -c calamus -s p -l preview -d 'Open in read-only preview mode'
complete -c calamus -l help              -d 'Show help options'
complete -c calamus -l help-all          -d 'Show all help options'
complete -c calamus -l help-gapplication -d 'Show GApplication options'

# Positional arguments: complete markdown files
complete -c calamus -F -r --condition 'not __fish_seen_argument -s p -l preview'
