import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import styles from './AppShell.module.css'

const NAV_ITEMS = [
  { to: '/folders', label: '收藏夹' },
  { to: '/import', label: '导入' },
  { to: '/tasks', label: '任务' },
  { to: '/items', label: '知识库' },
  { to: '/history', label: '对话历史' },
]

export default function AppShell() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('bilirag:sidebar') === '1',
  )

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev
      localStorage.setItem('bilirag:sidebar', next ? '1' : '0')
      return next
    })
  }

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.logo}>◆ BiliRag</div>
        <div className={styles.topActions}>
          <button type="button" className={styles.loginBtn}>
            登录
          </button>
          <Link to="/settings" className={styles.settingsBtn} title="设置">
            ⚙
          </Link>
        </div>
      </header>

      <div className={styles.body}>
        <aside className={collapsed ? styles.sidebarCollapsed : styles.sidebar}>
          <button type="button" className={styles.toggle} onClick={toggle}>
            ☰
          </button>
          {!collapsed && (
            <nav className={styles.nav}>
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) => (isActive ? styles.navItemActive : styles.navItem)}
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          )}
        </aside>

        <main className={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
