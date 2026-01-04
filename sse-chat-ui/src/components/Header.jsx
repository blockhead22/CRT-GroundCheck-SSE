import React, { useState } from 'react';
import { motion } from 'framer-motion';

function Header() {
  const [showMenu, setShowMenu] = useState(false);

  const handleClear = async () => {
    if (window.confirm('Clear chat history?')) {
      try {
        await fetch('/api/chat/history', { method: 'DELETE' });
        window.location.reload();
      } catch (error) {
        console.error('Error clearing history:', error);
      }
    }
  };

  return (
    <motion.header
      className="border-b border-darkBorder bg-darkBg px-4 py-4"
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="max-w-2xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-green-400 bg-clip-text text-transparent">
            SSE Chat
          </h1>
          <p className="text-sm text-gray-400 mt-1">Evidence Contradiction Explorer</p>
        </div>

        <div className="relative">
          <motion.button
            onClick={() => setShowMenu(!showMenu)}
            className="p-2 hover:bg-darkCard rounded-lg transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            ⚙️
          </motion.button>

          {showMenu && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -5 }}
              className="absolute right-0 mt-2 w-48 bg-darkCard border border-darkBorder rounded-lg shadow-lg z-10"
            >
              <button
                onClick={handleClear}
                className="w-full text-left px-4 py-2 hover:bg-darkBorder transition-colors text-sm text-red-400"
              >
                Clear Chat History
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </motion.header>
  );
}

export default Header;
