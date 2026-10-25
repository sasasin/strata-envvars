# `STRATA_HANDOFF_PIPE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。作業開始時点の Strata リポジトリは `main` の同 SHA で、未追跡の `nohup.out` があった。

## 役割

複数 GPU の prompt layer split で、ある段の出力 chunk を次段へ渡す host pinned buffer の転送を複数の行片に分ける設定です。既定の一括コピー経路では、出力の device-to-host コピー全体を待ってから次段を開始します。有効時は各片のコピー後に CUDA event を記録し、host は chunk の計算完了 event まで待って次段を起動します。次段は片ごとの event を GPU stream 上で待ってから host-to-device コピーを行うため、前段の残りの download と次段の upload を重ねられる構成です。転送先の値と行位置は同じです。

この設定は `src/prefill/prefill.cpp` の prompt prefill 経路にあり、decode の設定ではありません。`strata_prefill` は CUDA/HIP の構成で同じ `prefill.cpp` をビルド対象にします（CUDA API 名は HIP 構成で互換層を通ります）。実際にイベントを作るのは `next_ != nullptr` の段だけです。

## 値と判定

`std::getenv` で取得した値を `std::atoi` に渡し、結果 `p` が 2 以上なら `min(p, 16)` を使用します。それ以外は 0 として一括コピー経路を使います。文字列全体の妥当性検査はありません。

| 環境値 | 変換と動作 |
|---|---|
| 未設定 | `p=0`。一括コピー経路 |
| 空文字、数字に変換できない文字列 | `atoi` の結果は 0。一括コピー経路 |
| `0`, `1`, 負の数 | 2 未満なので一括コピー経路 |
| `2`〜`16` | 指定した片数を使う |
| `17` 以上 | 16 に clamp して使う |
| 数字の後ろに文字がある値（例: `3x`） | `atoi` が先頭の数値部分を変換するため、3 片を使う |

先頭の空白や符号も `atoi` の変換規則に従います。環境変数を読み込む関数内の `static const int` に結果を保存するため、最初に `handoff_pipe_pieces()` が呼ばれた後のプロセス内変更は反映されません。通常、この関数は `Prefill::init` 中、後続段がある場合に呼ばれます。

根拠: `src/prefill/prefill.cpp:356-364,1257-1271`。

## 有効になる条件

- prompt 経路が複数 GPU の layer split で、当該 `Prefill` に後続段があること。`generate.cpp` は各 GPU 段に次段を設定し、複数 GPU の先頭経路にも最初の段を設定します。
- 変換結果が 2 以上であること。
- 分割イベントを初期化できること。作成に失敗すると `Prefill::init` は失敗し、`prefill: the layer split's hand-off events (STRATA_HANDOFF_PIPE)` をエラーとして返します。一括コピーへ黙って fallback する処理はありません。

単一 GPU または split の最終段には後続段がないため、この分割 hand-off は発生しません。ソース上、分割数が正でも各 hand-off chunk の一部が空 (`nr == 0`) なら、その片の memcpy は省き event のみを記録します。

## 実行時の詳細

各段は hand-off 用の pinned host buffer を2個用意し、片ごとの event と chunk 完了 event も buffer ごとに保持します。イベントは timing 無効で作成されます。前段は現在の stream で chunk 完了 event を記録し、続けて各片を device から pinned buffer に非同期コピーし、コピー後に片 event を記録します。host は chunk 完了 event だけを同期して、checkpoint 等の `on_stage_chunk` 処理と先行する次段 run の回収を行います。その後、次段の `run_impl` を起動します。

次段は受け取った片 event ごとに自身の stream で `cudaStreamWaitEvent` を積み、chunk 全体が一度に処理される場合は対応する host buffer 範囲を片ごとに非同期 upload します。次段の chunk が受け取った全体より小さい場合は、片 event をすべて待ってから必要範囲を一括 upload します。API 呼び出しの失敗時は hand-off upload のエラーを返します。

後続段の起動スレッドには `STRATA_HANDOFF_PIPE_WORKER` も関係します。この別変数は、片数が有効なとき既定で persistent worker を使い、`atoi` 結果が 0 のとき `std::async` による chunk ごとの thread 起動に戻します。`STRATA_HANDOFF_PIPE` 自体の片分割判定とは別の設定です。worker は遅延生成され、`Prefill::release()` で停止・join されます。

根拠: `src/prefill/prefill.cpp:371-417,1045-1059,2499-2527,4581-4629`; `include/strata/prefill/prefill.hpp:244-266`。

## 文書との照合

`docs/BATCHING.md:124` は layer split で prompt chunk を 2〜16 片に分け、event で同期し persistent thread を使う設定と要約しています。ソース上では worker の有効/無効は `STRATA_HANDOFF_PIPE_WORKER` に分離されています。続く表は 4x R9700 32 GB / HIP、IQ3_S の expert 全常駐、layer split 12,25,37、3 回の interleaved rounds で、複数の「switches above」をまとめて使った場合を比較しています。基準は 0.1.44.1 の 8 slots、対照は同じ build の 16 slots（switch なし / 表記された全 switch 有効）です。この表から `STRATA_HANDOFF_PIPE` 単独の効果は分離できず、本調査では再測定していません。

## 根拠

- 値の取得、変換、上限: `src/prefill/prefill.cpp:356-364`。
- 後続段の初期化条件と event 作成: `src/prefill/prefill.cpp:1257-1271`。
- layer split の prompt path と `next_` 設定: `src/program/generate.cpp:8193-8221`; `include/strata/prefill/prefill.hpp:210-213`。
- 片ごとの upload wait: `src/prefill/prefill.cpp:2499-2527`。
- 前段の片ごとの download と次段起動: `src/prefill/prefill.cpp:4581-4629`。
- build 対象: `CMakeLists.txt:679-685`。
