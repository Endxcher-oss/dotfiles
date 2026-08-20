local lazypath = vim.fn.stdpath("data") .. "/lazy/lazy.nvim"
if not (vim.uv or vim.loop).fs_stat(lazypath) then
  local lazyrepo = "https://github.com/folke/lazy.nvim.git"
  local out = vim.fn.system({ "git", "clone", "--filter=blob:none", "--branch=stable", lazyrepo, lazypath })
  if vim.v.shell_error ~= 0 then
    vim.api.nvim_echo({
      { "Failed to clone lazy.nvim:\n", "ErrorMsg" },
      { out, "WarningMsg" },
      { "\nPress any key to exit..." },
    }, true, {})
    vim.fn.getchar()
    os.exit(1)
  end
end
vim.opt.rtp:prepend(lazypath)     
-- Make sure to setup `mapleader` and `maplocalleader` before
-- loading lazy.nvim so that mappings are correct.
-- This is also a good place to setup other settings (vim.opt)
vim.g.mapleader = " "

vim.o.updatetime = 250

vim.opt.shortmess:append("I")

--vim.cmd "syntax on"
vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.cursorline = true

-- Case insensitive searching when no upper case character is present
vim.opt.ignorecase = true
vim.opt.smartcase = true

vim.opt.swapfile = false
vim.opt.splitbelow = true
vim.opt.splitright = true
vim.opt.expandtab = true
vim.opt.tabstop = 4 
vim.opt.shiftwidth = 4

vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

-- Custom keybindings
local map = vim.api.nvim_set_keymap
local opts = { noremap = true, silent = true }
map("n", "<leader>h", ":set hlsearch!<CR>", opts)     -- Toggle search highlight
-- map("n", "<leader>s", ":set spell!<CR>", opts)        -- Toggle spell check

-- Tab navigation
map("n", "<leader>t", ":tabnew<CR>", opts)  -- Open new tab
map("n", "<leader>p", ":tabprev<CR>", opts) -- Go to previous tab
map("n", "<leader>n", ":tabnext<CR>", opts) -- Go to next tab

-- Reload configuration
map("n", "<leader>r", ":source ~/.config/nvim/init.lua<CR>", opts)

-- Splits
map("n", "<leader>x", ":split<CR>", opts)              -- Horizontal split
map("n", "<leader>v", ":vsplit<CR>", opts)             -- Vertical split

-- Split navigation with Ctrl + h/j/k/l
-- map("n", "<C-h>", "<C-w>h", opts)
-- map("n", "<C-j>", "<C-w>j", opts)
-- map("n", "<C-k>", "<C-w>k", opts)
-- map("n", "<C-l>", "<C-w>l", opts)

-- Split resizing with Ctrl + y/u/i/o
--map("n", "<C-y>", ":vertical resize -2<CR>", opts)
--map("n", "<C-u>", ":resize +2<CR>", opts)
--map("n", "<C-i>", ":resize -2<CR>", opts)
--map("n", "<C-o>", ":vertical resize +2<CR>", opts)

map("n", "<leader>e", ":NvimTreeToggle<CR>", opts)
map("n", "<leader>x", ":bd<CR>", opts) 
map("n", "<C-s>", ":w<CR>", opts)
map("n", "<C-q>", ":q<CR>", opts)
map("v", "<leader>y", "\"+y", opts)

-- H / L → 光标到行首 / 行尾
map('n', 'H', '0', opts)      -- 行首
map('n', 'L', '$', opts)      -- 行尾

-- J / K → 下一页 / 上一页（全屏翻页）
map('n', 'J', '<C-f>', opts)  -- 向下翻页
map('n', 'K', '<C-b>', opts)  -- 向上翻页

-- Ctrl+h / Ctrl+l → BufferLine 移动标签（需安装 nvim-bufferline.lua）
map('n', '<C-h>', ':BufferLineCyclePrev<CR>', opts)
map('n', '<C-l>', ':BufferLineCycleNext<CR>', opts)

-- Redo similar to Helix
vim.keymap.set({ 'n', 'v' }, 'U', '<C-r>')

require("lazy").setup({
  spec = {
        {
            'nvim-lualine/lualine.nvim',
            dependencies = { 'nvim-tree/nvim-web-devicons' },
            opts = {
                sections = {
                    lualine_c = { { 'filename', path = 3 } },
                    lualine_x = { 'encoding', 'filetype' },
                },
                extensions = { 'nvim-tree' },
            },
        },
        {
            "folke/tokyonight.nvim",
            lazy = false,
            priority = 1000,
            config = function()
            require('tokyonight').setup {
                styles = { functions = { bold = true } } }
            end,
        },
        {
            'akinsho/bufferline.nvim',
            dependencies = 'nvim-tree/nvim-web-devicons',
            opts = {},
        },
        {
            'windwp/nvim-autopairs',
            event = "InsertEnter",
            opts = {},
        },
        {
            "lukas-reineke/indent-blankline.nvim",
            event = "VeryLazy",
            main = "ibl",
            ---@module "ibl" @type ibl.config
            opts = {}, 
        },
        {
            "nvim-tree/nvim-tree.lua",
            dependencies = {"nvim-tree/nvim-web-devicons"},
            opts = {
                actions = { open_file = { quit_on_open = true } }
            },
        },
        {
            "selimacerbas/markdown-preview.nvim",
            dependencies = { "selimacerbas/live-server.nvim" },
            ft = { "markdown" },
            config = function()
            require("markdown_preview").setup({
            -- all optional; sane defaults shown
            instance_mode = "takeover",  -- "takeover" (one tab) or "multi" (tab per instance)
            port = 0,                    -- 0 = auto (8421 for takeover, OS-assigned for multi)
            open_browser = true,
            default_theme = "dark",      -- "dark" or "light"; initial preview theme
            debounce_ms = 300,
            })
            end,
        },
        {   
		    "catppuccin/nvim", name = "catppuccin", priority = 1000,
            config = function()
                require('catppuccin').setup ({
                    flavour = 'mocha',
                    transparent_background = true,
                    highlight_overrides = {
                        mocha = function(mocha)
                            return { LineNr = { fg = mocha.text }, 
                                     CursorLineNr = { fg = mocha.yellow, style = { "bold" } }
                            }
                        end
                    }
                })
            end
        }
  },
  install = { colorscheme = { "default" } },
  checker = { enabled = false },
})
vim.cmd[[colorscheme catppuccin]]
