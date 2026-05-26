import os
import tempfile
import unittest

from backend.zsxq_columns_database import ZSXQColumnsDatabase


class SnowflakeIdSerializationTest(unittest.TestCase):
    def test_column_topic_ids_are_returned_as_strings(self):
        topic_id = 82811852151825212
        group_id = 88851415151812
        column_id = 12345678901234567

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "columns.db")
            db = ZSXQColumnsDatabase(db_path)
            try:
                db.insert_column(
                    group_id,
                    {
                        "column_id": column_id,
                        "name": "Column",
                        "statistics": {"topics_count": 1},
                    },
                )
                db.insert_column_topic(
                    column_id,
                    group_id,
                    {
                        "topic_id": topic_id,
                        "title": "Topic",
                        "text": "Body",
                    },
                )
                db.insert_topic_detail(
                    group_id,
                    {
                        "topic_id": topic_id,
                        "type": "talk",
                        "title": "Topic",
                        "talk": {"text": "Body"},
                    },
                )

                topics = db.get_column_topics(column_id)
                column = db.get_column(str(column_id))
                detail = db.get_topic_detail(str(topic_id))

                self.assertEqual(str(topic_id), topics[0]["topic_id"])
                self.assertIsInstance(topics[0]["topic_id"], str)
                self.assertEqual(str(column_id), topics[0]["column_id"])
                self.assertIsInstance(topics[0]["column_id"], str)
                self.assertEqual(str(column_id), column["column_id"])
                self.assertIsInstance(column["column_id"], str)
                self.assertEqual(str(topic_id), detail["topic_id"])
                self.assertIsInstance(detail["topic_id"], str)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
