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
-- vim.o.ttimeoutlen = 50   -- 等待按键码（如 Esc 转义）的超时，一般设短些

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

-- vim.g.loaded_netrw = 1
-- vim.g.loaded_netrwPlugin = 1


-- 宏
-- vim.cmd('let @a = "Hi--\\<Esc>j"') -- 批量注释

require("lazy").setup({
  spec = {
--------------------- Start plugin definitions -------------------------------------
        {
          'stevearc/oil.nvim',
          ---@module 'oil'
          ---@type oil.SetupOpts
          opts = {},
          -- Optional dependencies
          dependencies = { "nvim-tree/nvim-web-devicons" },
          -- dependencies = {  }, -- use if you prefer nvim-web-devicons
          -- Lazy loading is not recommended because it is very tricky to make it work correctly in all situations.
          lazy = false,
	},
	{ 
            "folke/which-key.nvim",
            event = "VeryLazy",
            opts = {
                preset = "helix",
            },
            keys = {
                {
                "<leader>?",
                function()
                    require("which-key").show({ global = false })
                end,
                desc = "Buffer Local Keymaps (which-key)",
                },
            },
        },
        -- {
        --     'numToStr/Comment.nvim',
        --     config = function()
        --     require('Comment').setup()
        --     end
        -- },
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
        -- {
        --     "nvim-tree/nvim-tree.lua",
        --     dependencies = {"nvim-tree/nvim-web-devicons"},
        --     opts = {
        --         actions = { open_file = { quit_on_open = true } }
        --     },
        -- },
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
        },
  },------------------ End plugin definitions -----------------------------
  install = { colorscheme = { "default" } },
  checker = { enabled = false },
})

vim.cmd[[colorscheme catppuccin]]

-- Custom keybindings
local map = vim.keymap.set
local opts = { silent = true }
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

map("n", "<leader>e", ":NvimTreeToggle<CR>", opts)
map("n", "<leader>x", ":bd!<CR>", opts) 
map({"n", "i", "v"}, "<C-s>", "<Esc>:w<CR>", opts)
map("n", "<C-q>", ":q<CR>", opts)
map("v", "<leader>y", "\"+y", opts)

-- H / L → 光标到行首 / 行尾
map('n', 'H', '0', opts)      -- 行首
map('n', 'L', '$', opts)      -- 行尾

map('i', '<A-j>', '<Down>', opts)
map('i', '<A-k>', '<Up>', opts)
map('i', '<A-h>', '<Left>', opts)
map('i', '<A-l>', '<Right>', opts)

-- J / K → 下一页 / 上一页（全屏翻页）
map({'n', 'v'}, 'J', '<C-d>', opts)  -- 向下翻页
map({'n', 'v'}, 'K', '<C-u>', opts)  -- 向上翻页
map({'n', 'v'}, '<C-d>', '<C-f>', opts)
map({'n', 'v'}, '<C-u>', '<C-b>', opts)
-- Ctrl+h / Ctrl+l → BufferLine 移动标签（需安装 nvim-bufferline.lua）
map('n', '<C-h>', ':BufferLineCyclePrev<CR>', opts)
map('n', '<C-l>', ':BufferLineCycleNext<CR>', opts)

-- vim.cmd('nmap <leader>c gcc')
-- vim.cmd('vmap <leader>c gc')
vim.keymap.set('n', '<leader>c', 'gcc', { remap = true })
vim.keymap.set('v', '<leader>c', 'gc', { remap = true })
-- Redo similar to Helix
map({ 'n', 'v' }, 'U', '<C-r>')

vim.keymap.set('t', '<Esc><Esc>', '<C-\\><C-n>')
map('n', '<leader>t', ':term<CR>', opts)
vim.api.nvim_create_autocmd('TermOpen', {
    pattern = '*',
    callback = function()
        vim.wo.number = true
        vim.wo.relativenumber = true
    end,
})
