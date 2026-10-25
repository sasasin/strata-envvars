# `--stream-token`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--stream-token` |
| 別名 | なし |
| 値 | なし（真偽フラグ） |
| 既定値 | 無効。`--native` preset 使用時は自動で有効 |

## 役割

token 処理の一部を engine の session CUDA stream に enqueue する実験的な経路です。ソース内 usage も experimental と明記しています（`src/program/generate.cpp:840`）。

## 使い方

```sh
strata generate --pack ./pack/full --tokens "1,2,3" --stream-token
```

この例では `--stream-token` を指定しても token 値を渡しません。`--native MODEL.gguf` を指定する場合は preset がこのフラグを自動で有効にします（`src/program/generate.cpp:808-812, 2484, 3263`）。

## 値と既定値

- parser は値を消費せず `stream_token` を `true` にします。初期値は `false` です。同じフラグの重複指定も `true` の代入を繰り返すだけです（`src/program/generate.cpp:438, 2484`）。
- `--stream-token` 自体に値は不要です。直後に別の値を置くと、その値は別の argv として解析され、認識できなければ `unknown argument` と usage を stderr に出して終了コード2になります（`src/program/generate.cpp:2484, 2787-2792`）。
- このフラグ単独に追加の値検証はありません。ただし `--native-head-gguf` を指定したときは `--stream-token` が必要で、欠けていれば終了コード2です（`src/program/generate.cpp:3453-3456`）。

## 実行時の動作

- `stream_token` が真なら `token_stream` に `main_cs`（エンジンが作成する non-blocking CUDA stream）を渡し、偽なら既定 stream を渡します。`put_input` 内の embedding と残差 broadcast、PLE token finish、head、sampling がこの引数を使います（`src/program/generate.cpp:3985-3990, 7024-7040, 15910-15912, 15975-15977, 16038-16044`）。レイヤー計算の `session_token` / `session_loop` 呼び出しは、このフラグの分岐にかかわらず `main_cs` を渡します（`src/program/generate.cpp:15932-15949`）。
- フラグが有効なとき、embedding 後の `cudaDeviceSynchronize()` を省略します。また head 後の device-wide 同期も行いません（`src/program/generate.cpp:7040, 15984-15988`）。
- `--stream-token` だけを指定した場合、各位置の logits をホストに読み戻しません。sampling は device 上の `d_logits` を使って次 token を選び、その token ID はホストへコピーして stream を同期します（`src/program/generate.cpp:15994-16001, 16034-16044`）。
- `--check-logits` を併用すると全 logits を毎位置ホストへコピーして stream を同期し、全要素の有限値を検査します。`--dump-logits` でその位置の行を出力する場合も logits の読み戻し・有限値検査が行われます（`src/program/generate.cpp:15994-16020`）。通常は `read_logits` が真なので、`--stream-token` がない経路ではこの読み戻し・検査が常に行われます。同じ用途の別文書は [`--check-logits`](--check-logits.md) です。
- `--native` preset の後処理で `stream_token` を有効にします。したがって `--native` 使用時に明示的な `--stream-token` は不要です（`src/program/generate.cpp:3263-3268`）。

## 適用条件と副作用

- `--stream-token` 自体に backend / OS / build 条件の validation はありません。主な記述は CUDA stream と CUDA API による実装です（`src/program/generate.cpp:7024-7040, 15996-16001`）。各 backend・platform での実行可否や性能差は、このソース調査では実機確認していません。
- `--native-head-gguf` は stream-token 経路を要求します。`--native` preset はこれを満たします（`src/program/generate.cpp:860, 3263-3268, 3453-3456`）。
- `STRATA_HAVE_QWEN35` build で Qwen3.6-35B-A3B model を `--native` / `--model` に指定すると、通常 parser より前に `src/qwen35` の実装へ argv 全体が渡されます。その parser には `--stream-token` の定義がなく、`--serve` 以外でこの option を渡すと usage を表示して終了コード2になります。これは `src/program/generate.cpp` 側の通常 `strata generate` 経路と異なる適用条件です（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3735-3753, 3782-3795`）。
- `--stream-token` 単独では logits 出力ファイルを作りません。logits の readback / scan を有効にすると、毎位置の全語彙 logits を host に転送し同期する処理が加わります。ソースから時間・性能の定量値は確認できません（`src/program/generate.cpp:15994-16008`）。

## 出力とエラー

- フラグ単独の成功・失敗メッセージはありません。実行中は通常の position 表示など、他の処理による出力が発生します（例: `src/program/generate.cpp:15920-15922`）。
- token embedding、残差 broadcast、PLE finish、head の呼び出しや sampling token の読み戻しに失敗すると、該当エラーを stderr に出して終了コード1を返す経路があります（`src/program/generate.cpp:7026-7038, 15910-15912, 15975-15977, 16038-16044`）。
- `--check-logits` または選択位置の logits 読み戻しで CUDA 転送・stream 同期に失敗すると `strata generate: reading the logits back failed`、非有限値があれば位置と件数を stderr に出して終了コード1です（`src/program/generate.cpp:15996-16008`）。
- `--native-head-gguf` を stream-token なしで使うと `--native-head-gguf requires --stream-token` を stderr に出して終了コード2です（`src/program/generate.cpp:3453-3456`）。

## 根拠

- `src/program/generate.cpp:438, 840, 2484` — 既定値、usage、parser。
- `src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3735-3753, 3782-3795` — Qwen3.6 family dispatch と別 parser。
- `src/program/generate.cpp:3263-3268, 3453-3456` — `--native` による自動有効化と native head の要件。
- `src/program/generate.cpp:3985-3990, 7024-7040, 15910-15949` — stream 選択、入力、PLE、レイヤー処理。
- `src/program/generate.cpp:15975-16020, 16034-16044` — head 同期、logits の読み戻し・検査・出力、sampling。

同一 revision のビルド済み CLI `--help` は調査していません。ソース内 usage と parser を照合しました。公式 Release artifact や backend / platform ごとの実行結果は確認していません。
