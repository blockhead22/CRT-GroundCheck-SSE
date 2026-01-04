import React from 'react';
import { motion } from 'framer-motion';

function TypingIndicator() {
  return (
    <div className="flex gap-2 p-4 rounded-lg bg-darkCard border border-darkBorder">
      <motion.span
        className="w-2 h-2 bg-primary rounded-full"
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.4, repeat: Infinity }}
      />
      <motion.span
        className="w-2 h-2 bg-primary rounded-full"
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.4, repeat: Infinity, delay: 0.2 }}
      />
      <motion.span
        className="w-2 h-2 bg-primary rounded-full"
        animate={{ opacity: [0.4, 1, 0.4] }}
        transition={{ duration: 1.4, repeat: Infinity, delay: 0.4 }}
      />
    </div>
  );
}

export default TypingIndicator;
