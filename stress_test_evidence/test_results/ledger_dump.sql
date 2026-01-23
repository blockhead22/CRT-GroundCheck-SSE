BEGIN TRANSACTION;
CREATE TABLE conflict_resolutions (
                ledger_id TEXT PRIMARY KEY,
                resolution_method TEXT NOT NULL,
                chosen_memory_id TEXT,
                user_feedback TEXT,
                timestamp REAL NOT NULL,
                FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
            );
CREATE TABLE contradiction_worklog (
                ledger_id TEXT PRIMARY KEY,
                first_asked_at REAL,
                last_asked_at REAL,
                ask_count INTEGER DEFAULT 0,
                last_user_answer TEXT,
                last_user_answer_at REAL
            );
CREATE TABLE contradictions (
                ledger_id TEXT PRIMARY KEY,
                timestamp REAL NOT NULL,
                old_memory_id TEXT NOT NULL,
                new_memory_id TEXT NOT NULL,
                drift_mean REAL NOT NULL,
                drift_reason REAL,
                confidence_delta REAL,
                status TEXT NOT NULL,
                contradiction_type TEXT DEFAULT 'conflict',
                affects_slots TEXT,
                query TEXT,
                summary TEXT,
                resolution_timestamp REAL,
                resolution_method TEXT,
                merged_memory_id TEXT,
                metadata TEXT
            );
INSERT INTO "contradictions" VALUES('contra_1769129543366_1526',1.769129543366747857e+09,'mem_1769129531881_135','mem_1769129542254_890',4.502704567155079163e-01,NULL,0.0,'open','conflict','employer','I work at Amazon','User contradiction: I work at Microsoft... vs I work at Amazon...',NULL,NULL,NULL,NULL);
INSERT INTO "contradictions" VALUES('contra_1769129592101_7307',1769129592.10135,'mem_1769129573565_7037','mem_1769129585744_7970',3.659179798256557702e-01,NULL,0.0,'open','conflict','location','I live in New York','User contradiction: I live in Seattle... vs I live in New York...',NULL,NULL,NULL,NULL);
INSERT INTO "contradictions" VALUES('contra_1769129703335_178',1.769129703335940122e+09,'mem_1769129697463_4585','mem_1769129703171_431',3.73382686240916195e-01,NULL,0.0,'open','conflict','name','I''m married','User name changed: I''m single... vs I''m married...',NULL,NULL,NULL,NULL);
INSERT INTO "contradictions" VALUES('contra_1769129909016_4894',1.769129909016917706e+09,'mem_1769129703171_431','mem_1769129908936_7262',6.223425832982381057e-01,NULL,0.0,'open','conflict','name','I''m left-handed','User name changed: I''m married... vs I''m left-handed...',NULL,NULL,NULL,NULL);
INSERT INTO "contradictions" VALUES('contra_1769129914747_2609',1.769129914747258901e+09,'mem_1769129908936_7262','mem_1769129914713_9787',3.841604510118223902e-02,NULL,0.0,'open','conflict','name','I''m right-handed','User name changed: I''m left-handed... vs I''m right-handed...',NULL,NULL,NULL,NULL);
INSERT INTO "contradictions" VALUES('contra_1769130087006_8473',1.769130087006575346e+09,'mem_1769129597886_3227','mem_1769130080256_4434',2.364341337535539322e-01,NULL,0.0,'open','refinement','programming_language','I prefer tea over coffee','User contradiction: I prefer coffee... vs I prefer tea over coffee...',NULL,NULL,NULL,NULL);
CREATE TABLE reflection_queue (
                queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                ledger_id TEXT NOT NULL,
                volatility REAL NOT NULL,
                priority TEXT NOT NULL,
                context_json TEXT,
                processed INTEGER DEFAULT 0,
                FOREIGN KEY (ledger_id) REFERENCES contradictions(ledger_id)
            );
INSERT INTO "reflection_queue" VALUES(1,1.769129543388051033e+09,'contra_1769129543366_1526',5.68398095296866357e-01,'medium','{"query": "I work at Amazon", "drift": 0.4502704567155079, "intent_align": 0.8, "memory_align": 0.46673216687114394}',0);
INSERT INTO "reflection_queue" VALUES(2,1.769129592258085966e+09,'contra_1769129592101_7307',5.837855082756113755e-01,'medium','{"query": "I live in New York", "drift": 0.36591797982565577, "intent_align": 0.8, "memory_align": 0.30395954268834147}',0);
INSERT INTO "reflection_queue" VALUES(3,1.769130087066295385e+09,'contra_1769130087006_8473',5.139726685948902141e-01,'medium','{"query": "I prefer tea over coffee", "drift": 0.23643413375355393, "intent_align": 0.8, "memory_align": 0.42783028612470375}',0);
CREATE INDEX idx_contradictions_status 
            ON contradictions(status)
        ;
CREATE INDEX idx_contradictions_old_memory 
            ON contradictions(old_memory_id)
        ;
CREATE INDEX idx_contradictions_new_memory 
            ON contradictions(new_memory_id)
        ;
CREATE INDEX idx_reflection_queue_processed 
            ON reflection_queue(processed, priority)
        ;
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('reflection_queue',3);
COMMIT;
