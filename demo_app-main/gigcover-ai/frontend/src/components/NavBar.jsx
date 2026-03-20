import { Link, NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuth } from '../context/AuthContext'

const navItemClass = ({ isActive }) =>
  `px-4 py-2 rounded-full text-sm font-semibold transition ${
    isActive
      ? 'bg-white/70 text-slate-800 shadow-md'
      : 'text-slate-700 hover:bg-white/60 hover:shadow-sm'
  }`

export default function NavBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <motion.header
      initial={{ y: -16, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="sticky top-4 z-40 mx-auto mt-4 w-[94%] max-w-6xl"
    >
      <div className="glass flex flex-wrap items-center justify-between gap-3 rounded-2xl px-4 py-3 sm:px-5">
        <Link to="/" className="font-space text-xl font-bold text-slate-900">
          GigCover AI
        </Link>

        <nav className="flex flex-wrap items-center gap-2">
          <NavLink to="/" className={navItemClass}>
            Home
          </NavLink>
          <NavLink to="/dashboard" className={navItemClass}>
            Dashboard
          </NavLink>
          {!user && (
            <>
              <NavLink to="/login" className={navItemClass}>
                Login
              </NavLink>
              <Link
                to="/signup"
                className="rounded-xl px-4 py-2 text-sm font-semibold text-black shadow-sm transition duration-300 hover:brightness-95"
                style={{ background: 'linear-gradient(120deg, #ffc107 0%, #ffd54f 100%)' }}
              >
                🚀 Get Covered
              </Link>
            </>
          )}
          {user && (
            <button
              onClick={handleLogout}
              className="rounded-xl bg-[#ffc107] px-4 py-2 text-sm font-semibold text-black shadow-sm transition duration-300 hover:brightness-95"
            >
              Logout
            </button>
          )}
        </nav>
      </div>
    </motion.header>
  )
}
