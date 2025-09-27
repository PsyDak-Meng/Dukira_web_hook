import random
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TestModel:
    """
    Pseudo model class that acts as a placeholder for the actual model filter API.
    Randomly passes 50% of images for testing purposes.
    """
    
    def __init__(self):
        self.name = "TestModel"
        self.version = "1.0.0"
        
    async def analyze_image(self, image_data: bytes, image_url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze image and return mock results with 50% random pass rate.
        
        Args:
            image_data: Raw image bytes
            image_url: Original image URL
            
        Returns:
            Dict containing score and analysis, or None if processing fails
        """
        try:
            # Simulate processing time
            import asyncio
            await asyncio.sleep(0.1)  # 100ms simulated processing
            
            # Generate random score (50% chance to pass with score >= 0.7)
            will_pass = random.choice([True, False])
            
            if will_pass:
                # Generate passing score (0.7 - 1.0)
                score = random.uniform(0.7, 1.0)
                quality = "high" if score >= 0.85 else "medium"
            else:
                # Generate failing score (0.0 - 0.69)
                score = random.uniform(0.0, 0.69)
                quality = "low"
            
            # Mock analysis data
            analysis = {
                "quality": quality,
                "clarity": random.uniform(0.3, 1.0),
                "lighting": random.uniform(0.3, 1.0),
                "composition": random.uniform(0.3, 1.0),
                "background": random.choice(["clean", "cluttered", "neutral"]),
                "product_focus": random.choice([True, False]),
                "model_used": self.name,
                "confidence": random.uniform(0.8, 0.99)
            }
            
            result = {
                "score": score,
                "analysis": analysis
            }
            
            logger.info(f"TestModel analyzed image: score={score:.3f}, quality={quality}")
            return result
            
        except Exception as e:
            logger.error(f"TestModel processing failed: {str(e)}")
            return None
    
    def get_model_info(self) -> Dict[str, Any]:
        """Return information about the test model"""
        return {
            "name": self.name,
            "version": self.version,
            "type": "test_model",
            "description": "Pseudo model for testing - randomly passes 50% of images",
            "pass_rate": 0.5
        }