"""
ai/chunker.py
-------------
Günlük metinlerini vektör veritabanına kaydedilebilecek
anlamlı küçük parçalara (chunk) böler.
"""

def chunk_entry(date: str, content: str, max_words: int = 150) -> list[dict]:
    """
    Metni paragraflara böler. Eğer bir paragraf çok uzunsa onu da böler.
    Her parça için ID ve metadata (tarih) içeren bir sözlük döner.
    """
    if not content.strip():
        return []

    # Önce çift satır sonlarına göre (paragraf paragraf) böl
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    
    chunks = []
    chunk_index = 0
    
    for para in paragraphs:
        words = para.split()
        
        # Paragraf kısaysa tek parça olarak ekle
        if len(words) <= max_words:
            chunks.append({
                "id": f"{date}_{chunk_index}",
                "text": para,
                "metadata": {"date": date, "chunk_index": chunk_index}
            })
            chunk_index += 1
        else:
            # Paragraf çok uzunsa kelime kelime böl (overlap olmadan basit yaklaşım)
            for i in range(0, len(words), max_words):
                sub_para = " ".join(words[i:i + max_words])
                chunks.append({
                    "id": f"{date}_{chunk_index}",
                    "text": sub_para,
                    "metadata": {"date": date, "chunk_index": chunk_index}
                })
                chunk_index += 1

    return chunks
