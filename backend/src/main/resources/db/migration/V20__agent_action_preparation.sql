-- Nullable keys preserve legacy callers; new native preparations bind one tool call per owner/conversation.
ALTER TABLE agent_action
  ADD COLUMN original_amount DECIMAL(10,2) NULL,
  ADD COLUMN preparation_key VARCHAR(191) CHARACTER SET ascii COLLATE ascii_bin NULL,
  ADD COLUMN preparation_fingerprint VARCHAR(64) NULL,
  ADD COLUMN preparation_result JSON NULL,
  ADD COLUMN native_workflow_managed BOOLEAN NOT NULL DEFAULT FALSE,
  ADD UNIQUE KEY uk_agent_action_preparation (user_id, conversation_id, preparation_key);

-- Confirmation may update amount; fingerprints must retain the original quote.
UPDATE agent_action SET original_amount = amount WHERE original_amount IS NULL;
