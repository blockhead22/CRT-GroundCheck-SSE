import React from 'react';
import { motion } from 'framer-motion';
import SearchResults from './SearchResults';

function ChatMessage({ message }) {
  const isUser = message.role === 'user';
  const isError = message.isError;

  return (
    <motion.div
      className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4 flex-col ${isUser ? 'items-end' : 'items-start'}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
    >
      {/* Chat bubble */}
      <motion.div
        className={`max-w-xs lg:max-w-md px-4 py-3 rounded-lg ${
          isUser
            ? 'bg-primary text-white rounded-br-none'
            : isError
            ? 'bg-red-900 text-red-100 border border-red-700 rounded-bl-none'
            : 'bg-darkCard text-gray-200 border border-darkBorder rounded-bl-none'
        }`}
        layout
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.2 }}
      >
        <p className="text-sm leading-relaxed break-words whitespace-pre-wrap">{message.text}</p>
        <span className={`text-xs mt-2 block ${isUser ? 'text-green-100' : 'text-gray-500'}`}>
          {new Date(message.timestamp).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </motion.div>

      {/* Evidence panel - show if assistant has packet */}
      {!isUser && message.packet && (
        <div className="mt-4 w-full">
          <SearchResults 
            results={message.packet}
            loading={false}
            error={null}
          />
        </div>
      )}
    </motion.div>
  );
}

export default ChatMessage;
