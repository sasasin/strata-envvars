# `STRATA_TEST_SLOW_COPY_US`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

checkpoint の host-side コピーを意図的に遅くする診断用フックです。`src/core/conversation_copy.hpp` のコメントは tests only としていますが、値を読むコードにテスト専用のビルド条件はありません。設定すると、そのプロセスでこの共通コピー処理を通る checkpoint capture に遅延が加わります。

このコピー処理は、会話切り替え時に現在の会話を RAM に退避する処理と、session 保存時の checkpoint capture から呼ばれます。復元処理や GPU 上の K/V コピーを遅くする変数ではありません。

## 値と判定

値は `std::atol()` で `long` に変換され、その結果が 0 より大きい場合だけ遅延に使われます。文字列全体の厳密な検証はありません。

| 入力例 | 結果 |
|---|---|
| 未設定 | 0。遅延なし |
| 空文字、数値に変換できない文字列、`0`、`-5` | 0 以下。遅延なし |
| `250` | 250 マイクロ秒の遅延 |
| `250us`、`250.9` | `atol()` が先頭の整数部分を読むため、250 マイクロ秒 |

`atol()` のため、先頭の空白や符号を受け付け、数字の後ろに続く文字は変換結果に含まれません。先頭から数値として変換できない文字列は 0 になります。

## 有効になる条件

- 会話 checkpoint の vector が空でなく、`copy_beating()` が少なくとも1回のコピー区間を処理すること。
- 読み取った値が `long` として正しく変換され、かつ正であること。
- 環境変数の評価は `test_slow_copy_us()` 内の `static const long` に保存されます。最初にコピー区間が処理された時点の値がプロセス内で再利用され、その後の環境変更は反映されません。

変数が未設定でも checkpoint コピー自体は行われます。遅延だけが追加されません。空 vector はループ本体を通らないため helper を呼ばず、その時点では値の初回評価も起きません。

## 実行時の詳細

`copy_beating()` は各 vector を `max(1, 1 MiB / sizeof(T))` 要素ずつ複製します。各区間の複製後、設定値が正なら `std::this_thread::sleep_for(std::chrono::microseconds(us))` を実行し、その後 watchdog 用の `progress_beat()` を呼びます。したがって遅延は vector 1個あたりの合計ではなく、各処理区間ごとに追加されます。区間が 1 MiB 未満で終わる場合もその最後の区間に遅延します。

`copy_checkpoint_beating()` は `ids`, `imgs`, `gdn`, `ple`, `tails`, `dead`, `block_pos` の各 vector をこの方法で複製し、`stage_parts` も再帰的に処理します。`copy_checkpoints_beating()` は checkpoint 群すべてに適用します。呼び出し元は `conversation_snapshot_save()` と `conversation_snapshot_sources()` で、前者は会話の RAM 退避、後者は session file 保存時の metadata capture に使われます。

環境変数そのものによるログ出力やエラー処理はありません。正の値では各区間の待機時間が増え、待機後も `progress_beat()` が続きます。資料 `docs/DETAILS.md:655-665` は会話退避中の checkpoint copy が OS の page-in により長時間かかる事例と進捗通知を説明していますが、このテスト用環境変数の説明や測定値は記載していません。

## 根拠

- `src/core/conversation_copy.hpp:46-62`: tests only という注釈、`atol()`、static cache、区間サイズ、正値時の sleep、および progress 通知。
- `src/core/conversation_copy.hpp:67-87`: checkpoint vector 群と stage checkpoint への適用。
- `src/core/conversation_state.cpp:249-287`: snapshot save / session sources が checkpoint copy helper を呼ぶ箇所。
- `src/program/generate.cpp:7883-7892,8013-8025`: 会話切り替え時の退避経路と各 stage snapshot capture。
- `src/program/generate.cpp:10009-10024`: session 保存時の `conversation_snapshot_sources()` 呼び出し。
- `docs/DETAILS.md:655-665`: 会話退避の遅い checkpoint copy と watchdog 進捗に関する背景説明。
