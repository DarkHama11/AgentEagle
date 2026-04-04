# scripts/finetune_qlora.py
"""QLoRA Fine-Tuning para AgentEagle++ en RTX 3050 (4GB VRAM)."""
import torch
from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import Dataset, load_dataset
import os

# === CONFIGURACIÓN PARA 4GB VRAM (CRÍTICO) ===
MAX_SEQ_LENGTH = 1024
LORA_R = 8
LORA_ALPHA = 16
BATCH_SIZE = 1
GRADIENT_ACCUMULATION = 4
NUM_EPOCHS = 2
LEARNING_RATE = 2e-4

print("📦 Cargando dataset de ejemplos...")
try:
    dataset = load_dataset("json", data_files="data/AgentEagle_examples.jsonl", split="train")
    print(f"✅ {len(dataset)} ejemplos cargados")
except Exception as e:
    print(f"❌ Error cargando dataset: {e}")
    print("💡 Asegúrate de crear data/AgentEagle_examples.jsonl con ejemplos")
    exit(1)

print("🔄 Cargando modelo en 4-bit (QLoRA)...")
model_name = "unsloth/llama-3.2-3b-instruct"

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_name,
    max_seq_length=MAX_SEQ_LENGTH,
    load_in_4bit=True,
    token=None,
)

print("⚙️ Configurando adaptadores LoRA...")
model = FastLanguageModel.get_peft_model(
    model,
    r=LORA_R,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_ALPHA,
    lora_dropout=0,
    bias="none",
    use_gradient_checkpointing="unsloth",
)

print("🚀 Iniciando fine-tuning (esto tomará ~2-4 horas en RTX 3050)...")
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=dataset,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LENGTH,
    args=TrainingArguments(
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        warmup_steps=5,
        max_steps=60,
        learning_rate=LEARNING_RATE,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        output_dir="outputs/qlora_AgentEagle",
        optim="adamw_8bit",
        logging_steps=10,
        report_to="none",
    ),
)

trainer_stats = trainer.train()
print(f"✅ Entrenamiento completado. Loss final: {trainer_stats.training_loss:.4f}")

adapter_path = "adapters/AgentEagle_lora"
model.save_pretrained(adapter_path)
tokenizer.save_pretrained(adapter_path)
print(f"💾 Adaptadores guardados en: {adapter_path}")

print("\n🧪 Probando modelo fine-tuneado...")
FastLanguageModel.for_inference(model)
inputs = tokenizer("<|user|>¿Qué es CVE?<|end|>\n<|assistant|>", return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=256, use_cache=True)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))