import { useEffect } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { getAuthStatus, logout as logoutApi } from '../../api/auth'
import { useAuthStore } from '../../stores/auth'
import { useUiStore } from '../../stores/ui'
import LoginModal from '../LoginModal'
import Dropdown from '../ui/Dropdown'
import styles from './AppShell.module.css'

const NAV_ITEMS = [
  { to: '/folders', label: '收藏夹' },
  { to: '/import', label: '导入' },
  { to: '/items', label: '知识库' },
  { to: '/history', label: '对话历史' },
]

export default function AppShell() {
  const sidebarCollapsed = useUiStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useUiStore((s) => s.toggleSidebar)

  const loggedIn = useAuthStore((s) => s.loggedIn)
  const userName = useAuthStore((s) => s.userName)
  const loginModalOpen = useAuthStore((s) => s.loginModalOpen)
  const setLoggedIn = useAuthStore((s) => s.setLoggedIn)
  const logout = useAuthStore((s) => s.logout)
  const openLogin = useAuthStore((s) => s.openLogin)
  const closeLogin = useAuthStore((s) => s.closeLogin)

  const location = useLocation()

  useEffect(() => {
    getAuthStatus()
      .then((s) => setLoggedIn(s.logged_in, s.user_name, s.user_mid))
      .catch(() => {})
  }, [setLoggedIn])

  const isSettings = location.pathname.startsWith('/settings')
  const showWelcome = !loggedIn && !isSettings

  const handleLogout = async () => {
    try {
      await logoutApi()
    } catch {
      /* 忽略 */
    }
    logout()
  }

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.logo}>◆ BiliRag</div>
        <div className={styles.topActions}>
          {loggedIn ? (
            <Dropdown
              trigger={
                <button type="button" className={styles.accountBtn}>
                  {userName || '账号'} ▾
                </button>
              }
              items={[{ label: '退出登录', danger: true, onSelect: handleLogout }]}
            />
          ) : (
            <button type="button" className={styles.loginBtn} onClick={openLogin}>
              登录
            </button>
          )}
          <Link to="/settings" className={styles.settingsBtn} title="设置">
            ⚙
          </Link>
        </div>
      </header>

      <div className={styles.body}>
        <aside className={sidebarCollapsed ? styles.sidebarCollapsed : styles.sidebar}>
          <button type="button" className={styles.toggle} onClick={toggleSidebar}>
            ☰
          </button>
          {!sidebarCollapsed && (
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
          {showWelcome ? (
            <div className={styles.welcome}>
              <h1 className={styles.welcomeTitle}>BiliRag</h1>
              <p className={styles.welcomeDesc}>本地 B 站视频知识库</p>
              <p className={styles.welcomeSub}>提取收藏 → 结构化摘要 → 检索问答 → 导出笔记</p>
              <button type="button" className={styles.welcomeBtn} onClick={openLogin}>
                立即登录
              </button>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>

      <LoginModal open={loginModalOpen} onOpenChange={closeLogin} />
    </div>
  )
}
