import React, { useState } from 'react';
import { motion } from 'framer-motion';

function ChatInput({ value, onChange, onSend, disabled }) {
  const [isFocused, setIsFocused] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (value.trim() && !disabled) {
      onSend(value);
    }
  };

  return (
    <motion.form
      onSubmit={handleSubmit}
      className="px-4 py-4 border-t border-darkBorder bg-darkBg"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex gap-3 max-w-2xl mx-auto">
        <input
          type="text"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Ask anything about contradictions..."
          disabled={disabled}
          className={`flex-1 px-4 py-3 rounded-lg border bg-darkCard text-ececec placeholder-gray-500 focus:outline-none focus:ring-1 transition-all ${
            isFocused ? 'border-primary focus:ring-primary' : 'border-darkBorder'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        />
        <motion.button
          type="submit"
          disabled={disabled || !value.trim()}
          whileHover={{ scale: disabled ? 1 : 1.05 }}
          whileTap={{ scale: disabled ? 1 : 0.95 }}
          className={`px-4 py-3 rounded-lg font-medium transition-all ${
            disabled || !value.trim()
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-primary text-white hover:bg-green-600 active:scale-95'
          }`}
        >
          {disabled ? '...' : '⬆'}
        </motion.button>
      </div>
    </motion.form>
  );
}

export default ChatInput;
