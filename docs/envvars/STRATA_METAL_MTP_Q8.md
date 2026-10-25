# `STRATA_METAL_MTP_Q8`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal backend の MTP draft layer をロードするとき、適格な BF16 重みを Q8_0 に変換して使うかを選びます。既定では変換し、`STRATA_METAL_MTP_Q8=0` なら変換せず BF16 のまま使います。実装コメントでは draft step が読む重みのバイト数を半分にする狙いとされています。対象は MTP の draft 計算であり、通常の decode/verify window の重みを変換する設定ではありません。

MTP は `--mtp` が指定され、`--spec` が 2 以上の場合にロード対象になります。`--mtp` が空でない場合でも `--spec < 2` なら generate は MTP を無視します（`src/program/generate.cpp:4612-4616`）。Metal build では MTP load/draft が `strata::metal_engine` に委譲されます（`src/core/mtp.cpp:249-256,1516-1525`）。

## 値と判定

`Window::mtp_load()` 内で環境変数を読み、値が文字列全体で `"0"` と一致する場合だけ BF16 のままにします（`metal/src/engine/window.cpp:1506-1510`）。数値変換や先頭文字判定ではありません。

| 環境変数の状態 | 結果 |
|---|---|
| 未設定 | Q8_0 変換を行う |
| 空文字 | Q8_0 変換を行う（`"0"` とは一致しない） |
| `0` | 変換しない。元の BF16 重みを使う |
| `00`, `0 `, `false`, `1` など | Q8_0 変換を行う。文字列全体が `"0"` でないため |

この判定は MTP GGUF をロードするたびに行われます。環境値はその時点で取り込まれ、変換後の `mq8_` とテンソル対応表が Window に保持されるため、ロード後に環境を変更しても既にロード済みの MTP 重みには反映されません（`metal/src/engine/window.cpp:1489-1494,1506-1540`）。

## 有効になる条件

- Strata が Metal backend でビルドされ、MTP drafter を実際にロードする経路でのみ参照されます。CUDA/HIP の MTP 実装はこの変数を読みません（`src/core/mtp.cpp:249-258`）。
- 変換対象は MTP GGUF 内で、型が BF16、shape の次元数が 2 以上、かつ `shape[0]` が 32 の倍数であるテンソルに限られます。その他の BF16 tensor や別形式の tensor は変換されず、元の MTP weight buffer を参照します（`metal/src/engine/window.cpp:1511-1525`）。
- 適格テンソルについて要素数を shape の積として算出し、BF16 を float に dequantize してから Q8_0 に quantize します。Q8_0 用領域の各テンソル開始位置は 256 byte 単位に揃え、変換スレッド数は `hardware_concurrency()` を 1〜16 に制限します（`metal/src/engine/window.cpp:1512-1539`）。
- MTP の hyper-connection 読み出しは、down/up/inject の3テンソルがすべて Q8_0 の場合に Q8 用 kernel を選びます。通常の MTP GEMV も tensor の型と対応するバッファを選ぶため、変換された tensor だけ Q8_0 コピーを読みます（`metal/src/engine/window.cpp:1624-1652,1685-1703`）。

`STRATA_METAL_MTP_Q8=0` は MTP 自体を無効にせず、その重みの Q8_0 コピー生成を止めるだけです。MTP のロード自体は既定パスで `<rt-dir>/../mtp-q2_0.gguf` を使うか、別変数 `STRATA_METAL_MTP_GGUF` で指定したパスを読みます（`metal/src/engine/window.cpp:2524-2541`）。

## 実行時の詳細

変換は MTP GGUF を開き、norm buffer を用意して MTP kernel を compile した後、draft 用 Q8_0 buffer を構築するロード処理中に同期的に実行されます。各対象 tensor について、元の BF16 データを `ref::dequant()` で float 配列へ展開し、`ref::quantize_q8_0()` の出力を `mq8_` の該当 offset に格納します（`metal/src/engine/window.cpp:1489-1540`）。専用の有効/無効ログはありません。ロードが成功すると、通常の `strata metal: MTP draft layer from ...` ログが出ます（同:1618-1620）。

Q8_0 に変換したテンソルは `TQ()` が返す型・offset と `MB()` が返す buffer の組で参照します。別の変換されていない tensor は元の `Wm_` と GGUF tensor 情報を使います（`metal/src/engine/window.cpp:328-346`）。MTP が提案した token は verifier 側の処理に渡される draft 候補です。ここでは Q8_0 と BF16 の生成結果の同一性や、速度差を独自に測定していません。

## 根拠

- `metal/src/engine/window.cpp:1489-1540` — MTP load、厳密な `"0"` 判定、変換対象選別、Q8_0 copy の作成。
- `metal/src/engine/window.cpp:328-346,1624-1652,1685-1703` — 変換 tensor の型・buffer 選択と draft kernel dispatch。
- `src/core/mtp.cpp:249-256,1516-1525`、`src/program/generate.cpp:4612-4619` — Metal MTP load/draft の委譲と `--mtp` / `--spec` 条件。
- `docs/MAC.md:183-191` — `STRATA_METAL_MTP_Q8=0` を BF16 の draft matrix を使うスイッチとして記載。ソースでは未設定時に適格 BF16 tensor を Q8_0 化することを確認。
