# ~/.config/fish/config.fish

# Disable the fish greeting
set -U fish_greeting

# Colour theme
set --global fish_color_autosuggestion 707A8C
set --global fish_color_cancel --reverse
set --global fish_color_command 5CCFE6
set --global fish_color_comment 5C6773
set --global fish_color_cwd 73D0FF
set --global fish_color_cwd_root red
set --global fish_color_end F29E74
set --global fish_color_error FF3333
set --global fish_color_escape 95E6CB
set --global fish_color_history_current --bold
set --global fish_color_host normal
set --global fish_color_host_remote yellow
set --global fish_color_normal CBCCC6
set --global fish_color_operator FFCC66
set --global fish_color_param CBCCC6
set --global fish_color_quote BAE67E
set --global fish_color_redirection D4BFFF
set --global fish_color_search_match --bold --background=FFCC66
set --global fish_color_selection --bold --background=FFCC66
set --global fish_color_status red
set --global fish_color_user brgreen
set --global fish_color_valid_path --underline=single
set --global fish_pager_color_completion normal
set --global fish_pager_color_description B3A06D
set --global fish_pager_color_prefix normal --bold --underline=single
set --global fish_pager_color_progress brwhite --bold --background=cyan
set --global fish_pager_color_selected_background --background=FFCC66
set --global fish_pager_color_selected_completion
set --global fish_pager_color_selected_description
set --global fish_pager_color_selected_prefix

function fish_prompt --description 命令提示符
    set -l last_status $status
    set -l normal (set_color normal)
    set -l error_prefix ""

    # 上一条命令出错时，生成红色的错误状态信息（使用小括号，无空格）
    if test $last_status -ne 0
        set error_prefix (set_color red)"("$last_status")"(set_color normal)
    end

    # 根据用户类型决定提示符字符
    set -l suffix '$'
    if functions -q fish_is_root_user; and fish_is_root_user
        set suffix '#'
    end

    # 生成当前目录（使用 prompt_pwd 简化路径）
    set -l pwd_str (prompt_pwd -d 0)

    # 输出：当前目录 + 空格 + 错误状态（如果有）+ 提示符 + 空格
    echo -n -s $pwd_str\n $error_prefix $suffix $normal " "
end

function fish_title
    set -l ssh
    set -q SSH_TTY
    and set ssh "["(prompt_hostname | string sub -l 100 | string collect)"]"
    if set -q argv[1]
        echo -- $ssh (string sub -l 100 -- $argv[1]) (prompt_pwd -d 0)
    else
        set -l command (status current-command)
        if test "$command" = fish
            set command
        end
        echo -- $ssh (string sub -l 100 -- $command) (prompt_pwd -d 0)
    end
end

# Environment Variables
export EDITOR=hx
#export GTK_IM_MODULE=fcitx
#export QT_IM_MODULE=fcitx
export XMODIFIERS=@im=fcitx
export QT_LOGGING_RULES='*=false'

# Alias
alias ls='ls --color=auto --classify=auto --hyperlink=auto'
alias grep='grep --color=auto'
alias s='sudo'
alias se='sudo -e'
alias v='hx'
alias r='sudo pacman -Syu'
alias rmo='sudo pacman -Rsn $(pacman -Qtdq)'
alias f='fastfetch'
alias send='curl -F "c=@-" "https://fars.ee/"'
alias ll='ls -ahl'
alias la='ls -a'
alias l.='ls -d .*'
alias cx='mpv https://myradio24.org/69366.m3u'
alias jf='journalctl -f'
alias jb='journalctl -b'
alias jb-='journalctl -b -1'
alias paclean='paccache -rk0'
alias bye='systemctl hibernate'
alias conf='yadm'
alias sysconf='sudo yadm --yadm-dir /etc/yadm --yadm-data /etc/yadm/data'

# start KDE at login
if status --is-login
    if test -z "$DISPLAY" -a $XDG_VTNR = 1
        export LANG=zh_CN.UTF-8
        export LC_CTYPE=zh_CN.UTF-8
        export LC_NUMERIC=zh_CN.UTF-8
        export LC_TIME=zh_CN.UTF-8
        export LC_COLLATE=zh_CN.UTF-8
        export LC_MONETARY=zh_CN.UTF-8
        export LC_MESSAGES=zh_CN.UTF-8
        export LC_PAPER=zh_CN.UTF-8
        export LC_NAME=zh_CN.UTF-8
        export LC_ADDRESS=zh_CN.UTF-8
        export LC_TELEPHONE=zh_CN.UTF-8
        export LC_MEASUREMENT=zh_CN.UTF-8
        export LC_IDENTIFICATION=zh_CN.UTF-8
        export KWIN_USE_OVERLAYS=1
        export XMODIFIERS=@im=fcitx
        export QT_LOGGING_RULES='*=false'
        exec /usr/lib/plasma-dbus-run-session-if-needed /usr/bin/startplasma-wayland
    end
end
# Git information prompt
# set -g __fish_git_prompt_show_informative_status 1
# set -g __fish_git_prompt_hide_untrackedfiles 1

# set -g __fish_git_prompt_color_branch brmagenta
# set -g __fish_git_prompt_showupstream "informative"
# set -g __fish_git_prompt_char_upstream_ahead "↑"
# set -g __fish_git_prompt_char_upstream_behind "↓"
# set -g __fish_git_prompt_char_upstream_prefix ""

# set -g __fish_git_prompt_char_stagedstate "●"
# set -g __fish_git_prompt_char_dirtystate "✚"
# set -g __fish_git_prompt_char_untrackedfiles "…"
# set -g __fish_git_prompt_char_conflictedstate "✖"
# set -g __fish_git_prompt_char_cleanstate "✔"

# set -g __fish_git_prompt_color_dirtystate blue
# set -g __fish_git_prompt_color_stagedstate yellow
# set -g __fish_git_prompt_color_invalidstate red
# set -g __fish_git_prompt_color_untrackedfiles $fish_color_normal
# set -g __fish_git_prompt_color_cleanstate brgreen

# User binaries
fish_add_path ~/.local/bin

# Added by Antigravity CLI installer
set -gx PATH "/home/Endxcher/.local/bin" $PATH

fish_add_path /home/Endxcher/.local/share/pnpm/bin
