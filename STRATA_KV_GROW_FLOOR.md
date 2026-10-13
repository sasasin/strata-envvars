# `STRATA_KV_GROW_FLOOR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。Strata 所有の CUDA と SYCL 実装を確認した。外部ライブラリと GPU ドライバーが独自に読む環境変数は対象外。

## 役割

弾力的な K/V（elastic K/V）を拡張するとき、エキスパートキャッシュから K/V 用に明け渡すスロットの下限を指定する。既定値は128スロット。K/V 拡張に必要な VMM チャンクが足りない場合、実装はこの下限より上にあるキャッシュスロットを順に明け渡す。下限まで達してもチャンクが足りなければ、新しい VRAM チャンクを使って K/V を拡張する。

この変数だけで elastic K/V を有効にはしない。`--kv-grow` または `STRATA_KV_GROW` で同機能が要求され、単一 GPU、プロファイル済みエキスパート、全エキスパートの RAM 常駐、VMM 利用可能、非 batch、非 `--vram-elastic`、非 `--peer-device` などの条件を満たした経路でのみ、床値が使われる。

## 値と判定

CUDA と SYCL の `kvg_start()` は `std::getenv("STRATA_KV_GROW_FLOOR")` の結果を `std::atoll()` に渡し、変換結果が正の場合だけ `kvg.floor` に代入する。文字列全体の検証はなく、10進数として変換できた先頭部分が使われる。

| 値 | 結果 |
|---|---|
| 未設定 | 既定値128を使う |
| 空文字、数値に変換できない文字列、0、負数 | `atoll` の結果が正でないため既定値128を使う |
| 正の数値 | その正の整数をスロット数の下限として使う |
| 正の数値の後ろに文字が続く値（例: `256junk`） | `atoll` が変換した先頭の数値256を使う |

`atoll` は10進変換であり、全体一致、大文字小文字、後続文字の妥当性は確認しない。たとえば `12.5` は先頭の `12` に変換される。正の値に上限 clamp はない。

## 有効になる条件

- `STRATA_KV_GROW_FLOOR` は、elastic K/V が実際に開始した後の `kvg_start()` 内で読み取られる。elastic K/V が無効、または `kvg_start()` の開始条件を満たさない場合、この値は読まれず、挙動に影響しない。
- 開始条件は、elastic K/V が有効、エキスパートキャッシュに VMM range と device residency table があり、RAM 常駐エキスパートがあり、source が存在し、その時点の `kvg.floor` より `top` が大きいこと。`STRATA_KV_GROW_FLOOR` 自体を読むのはこの判定の後である。初回は `kvg.floor` が既定値128なので、設定値を128より大きくしても `top > 128` なら開始し、後続の拡張で新しい床値が使われる。逆に、初回は設定値を小さくしても `top <= 128` では開始条件を通らない。
- HIP では `src/core/vmm.cpp` の HIP 実装が `vmm_available()` を常に `false` にするため、上位の `--kv-grow` 判定で無効となり、この床値も使われない。

## 実行時の詳細

`kvg_start()` はプロンプト処理でキャッシュスロットを K/V に貸す経路、または貸し出しを使わずに開始する経路で呼び出される。開始条件を通った呼び出しは環境値を読み、正の値なら `kvg.floor` を上書きしてから、K/V の現在容量などを stderr に記録する。値は `static` cache ではなく `KvGrow` 状態に保存される。したがって、同じ状態で後続の `kvg_start()` 呼び出しがあれば環境値を再度読み、正の値なら上書きする一方、未設定や無効値では前回値を初期値128に戻さない。

`kvg_ensure()` は要求セル数を `STRATA_KV_GROW_STEP`（既定8192セル）単位に切り上げて必要な K/V チャンクを計算する。既存の余剰チャンクとキャッシュ内で解放可能なチャンクで足りなければ、`kvg.lo > kvg.floor` の間、下端スロットを解放してエキスパートを非 resident にするか、より低温のエキスパートを別スロットへ移す。その後、その範囲の VMM チャンクを K/V に渡す。床値に到達してもなお不足する分は新しいチャンクを要求するため、floor は K/V 拡張の上限でも、新規 VRAM 割当てを止める値でもない。

値そのものを表示する専用ログはない。機能が開始すると stderr に `strata generate: elastic K/V: ...` が出て、拡張時には `strata: K/V grown to ...` が出る。下限到達後に新規チャンクを使った場合、拡張ログには `- and new VRAM, the cache being at its floor` が付く。実行統計では `elastic K/V` のセル数、grow/trim 回数、明け渡したエキスパート数、再充填数を表示する。

## 根拠

- `src/program/generate.cpp:4224-4238`: `--kv-grow` と `STRATA_KV_GROW` の有効条件、VMM 条件、HIP を含む機能の入口、`STRATA_KV_GROW_INIT` の設定。
- `src/program/generate.cpp:6401-6424`: `kvg.floor` の既定値、開始条件、環境変数の読み取りと初期ログ。
- `src/program/generate.cpp:6426-6432,6450-6456`: 要求セルの切り上げ、利用可能チャンク数、床値を使ったスロット明け渡し条件。
- `src/program/generate.cpp:6491-6527`: 解放チャンクを K/V に渡す処理、新規チャンクの使用、拡張ログと失敗ログ。
- `src/program/generate.cpp:7356,12441-12446,12482-12485,12534-12537`: `kvg_start()` の呼び出し経路。
- `src/program/generate.cpp:13391-13394`: elastic K/V の実行統計。
- `sycl/src/program/generate.cpp:6056-6079,6081-6112,6201-6220`: SYCL 側の同じ床値、開始条件、拡張処理。値の判定と床値の用途は CUDA 実装と同じ。
- `src/core/vmm.cpp:154-168`: HIP では VMM を利用不可とする実装。
- `docs/DETAILS.md:260-264`: `--kv-grow` の概要と適用条件。`STRATA_KV_GROW_FLOOR` 固有の値・仕様は説明されていないため、上記の詳細は実装から確認した。
