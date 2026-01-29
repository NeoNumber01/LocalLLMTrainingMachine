import React, { ReactNode, useState, useEffect } from 'react';
import { useLocation, Link } from 'react-router-dom';
import CommandPalette from './CommandPalette';
import NotificationPanel from './NotificationPanel';
import { fetchUnreadCount } from '../lib/api';
interface LayoutProps {
  children: ReactNode;
}

const NavItem = ({ to, icon, label, active }: { to: string; icon: string; label: string; active: boolean }) => (
  <Link
    to={to}
    className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${active
      ? 'bg-primary/10 text-primary border border-primary/20'
      : 'text-gray-400 hover:text-white hover:bg-white/5'
      }`}
  >
    <span className={`material-symbols-outlined text-[20px] ${active ? 'fill-1' : ''}`}>{icon}</span>
    <span>{label}</span>
  </Link>
);

const Layout: React.FC<LayoutProps> = ({ children }) => {
  const location = useLocation();
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isNotificationPanelOpen, setIsNotificationPanelOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  // Load unread count
  useEffect(() => {
    const loadUnreadCount = async () => {
      try {
        const { count } = await fetchUnreadCount();
        setUnreadCount(count);
      } catch (e) {
        console.error('Failed to fetch unread count:', e);
      }
    };

    loadUnreadCount();
    // Poll every 30 seconds
    const interval = setInterval(loadUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut: Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  return (
    <div className="flex h-screen bg-background text-gray-100 overflow-hidden">
      {/* Command Palette */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
      />

      {/* Sidebar */}
      <aside className="w-64 bg-surface border-r border-border flex flex-col shrink-0 z-20">
        <div className="h-16 flex items-center gap-3 px-6 border-b border-border">
          <div className="w-8 h-8 rounded bg-gradient-to-br from-primary to-cyan-500 flex items-center justify-center text-white font-bold text-xs">
            NX
          </div>
          <span className="font-bold text-lg tracking-tight">Nexus AI</span>
        </div>

        <nav className="flex-1 flex flex-col gap-1 px-3 py-4 overflow-y-auto">
          <NavItem to="/" icon="dashboard" label="Dashboard" active={location.pathname === '/'} />
          <NavItem to="/runs" icon="play_circle" label="Runs" active={location.pathname.startsWith('/runs')} />
          <NavItem to="/playground" icon="chat" label="Playground" active={location.pathname.startsWith('/playground')} />
          <NavItem to="/evaluation" icon="science" label="Evaluation" active={location.pathname.startsWith('/evaluation')} />
          <div className="my-2 border-t border-border/50"></div>
          <NavItem to="/models" icon="deployed_code" label="Models" active={location.pathname.startsWith('/models')} />
          <NavItem to="/datasets" icon="database" label="Datasets" active={location.pathname.startsWith('/datasets')} />
          <NavItem to="/adapters" icon="extension" label="Adapters" active={location.pathname.startsWith('/adapters')} />
          <div className="my-2 border-t border-border/50"></div>
          <NavItem to="/compare" icon="compare_arrows" label="Compare" active={location.pathname.startsWith('/compare')} />
          <NavItem to="/reports" icon="bar_chart" label="Reports" active={location.pathname.startsWith('/reports')} />
          <NavItem to="/settings" icon="settings" label="Settings" active={location.pathname.startsWith('/settings')} />
        </nav>

        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/5 border border-border">
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-pink-500"></div>
            <div className="flex flex-col overflow-hidden">
              <span className="text-xs font-medium text-white truncate">Dev User</span>
              <span className="text-[10px] text-gray-500 truncate">Local Workspace</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 bg-surface/80 backdrop-blur border-b border-border flex items-center justify-between px-6 shrink-0 z-10">
          <div className="flex items-center gap-4 text-sm text-gray-500">
            {/* Simple Breadcrumbs Placeholder */}
            <span>Workspace</span>
            <span>/</span>
            <span className="text-white font-medium capitalize">{location.pathname === '/' ? 'Dashboard' : location.pathname.split('/')[1]}</span>
          </div>

          <div className="flex items-center gap-4">
            {/* Search Button - Opens Command Palette */}
            <button
              onClick={() => setIsCommandPaletteOpen(true)}
              className="relative hidden md:flex items-center gap-2 bg-black/20 border border-border rounded-lg px-3 py-1.5 text-sm text-gray-400 hover:text-white hover:border-gray-600 transition-all w-64"
            >
              <span className="material-symbols-outlined text-[18px]">search</span>
              <span className="flex-1 text-left">Search resources...</span>
              <kbd className="text-[10px] text-gray-500 border border-gray-700 rounded px-1.5 bg-gray-800">⌘K</kbd>
            </button>
            <div className="relative">
              <button
                onClick={() => setIsNotificationPanelOpen(!isNotificationPanelOpen)}
                className="relative p-2 text-gray-400 hover:text-white transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">notifications</span>
                {unreadCount > 0 && (
                  <span className="absolute top-1 right-1 min-w-[18px] h-[18px] bg-red-500 rounded-full border-2 border-surface text-[10px] text-white font-bold flex items-center justify-center">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>
              <NotificationPanel
                isOpen={isNotificationPanelOpen}
                onClose={() => setIsNotificationPanelOpen(false)}
                onUnreadCountChange={setUnreadCount}
              />
            </div>
            <Link to="/runs/new" className="bg-white text-black px-3 py-1.5 rounded-md text-sm font-medium hover:bg-gray-200 transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-[18px]">add</span>
              New Train
            </Link>
          </div>
        </header>

        <main className="flex-1 overflow-hidden relative">
          {children}
        </main>
      </div>
    </div>
  );
};

export default Layout;
