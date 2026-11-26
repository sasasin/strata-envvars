# `STRATA_OWNED_PRICE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

プロンプト処理がキャッシュからバッファを借りず、自分で確保する場合に、expert cache の VRAM 容量計算へ加えるプロンプトバッファの見積もり方を切り替える。値が文字列 `exact` のとき `Prefill::bytes_needed_owned` に基づく見積もりを使い、それ以外は従来式 `160 + chunk * 680 / 1024` MiB を使う。これはキャッシュ sizing の予約量を変えるもので、プロンプトバッファの実確保や生成内容を直接切り替える処理ではない（`engine/src/program/generate.cpp:9063-9070,9189-9203`、SYCL は `engine/sycl/src/program/generate.cpp:4842-4849,4858-4877`）。

同じ切替が CUDA/HIP 系の generate 実装と SYCL 実装にある。実際にどちらが使われるかはビルドされた backend による（`engine/src/program/generate.cpp:9063-9070`、`engine/sycl/src/program/generate.cpp:4842-4849`）。

## 値と判定

値は `std::getenv` で読み、`std::string(v) == "exact"` を比較する。文字列全体が大文字小文字も含めて完全一致するときだけ有効。数値変換、trim、先頭文字判定はしない。未設定、空文字、`1`、`true`、`EXACT`、`exact ` などはすべて従来式に戻る。比較はいずれも `owned_prefill_mib` 内の関数ローカル `static const bool` に初回評価結果を保存する（`engine/src/program/generate.cpp:9063-9067`、`engine/sycl/src/program/generate.cpp:4842-4846`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| CUDA/HIP 系または SYCL の当該 sizing 経路で、owned prompt buffer の見積もりが必要 | 従来式 `160 + chunk * 680 / 1024` MiB | `exact` | 空文字、`1`、`true`、`EXACT`、`exact ` など |

`exact` のときは owned buffer の必要 byte 数を MiB 単位で切り上げ、さらに 64 MiB を加えて予約量にする。従来式は整数演算で MiB 見積もりを算出する（`engine/src/program/generate.cpp:9065-9070`、`engine/sycl/src/program/generate.cpp:4844-4849`）。`bytes_needed_owned` はプロンプト経路の allocation を数える関数で、CUDA/HIP 実装では個々の owned allocation を 2 MiB 粒度で数え、SYCL 実装にも同名の計数関数がある（`engine/src/prefill/prefill.cpp:3713-3725`、`engine/sycl/src/prefill/prefill.cpp:2418-2431`）。

## 有効になる条件

- 対象 backend の `generate.cpp` が使われること。候補は CUDA/HIP 系 (`engine/src/program/generate.cpp`) と SYCL (`engine/sycl/src/program/generate.cpp`) の実装である。
- `owned_prefill_mib()` が呼ばれるとき `o.prefill_chunk > 0` かつ `pf_borrow == false` であること。この条件を満たさない場合、関数は環境変数を読む前に `0` を返す（`engine/src/program/generate.cpp:9063-9065`、`engine/sycl/src/program/generate.cpp:4842-4844`）。`pf_borrow` は `--no-prefill-borrow` がなく、expert profile がある場合に true となる（`engine/src/program/generate.cpp:6821`）。
- expert cache の自動 sizing ではこの予約量を含めて slot 数を計算する。CUDA/HIP 系では `--expert-cache auto` 相当の `o.expert_cache < 0` 枝で使う（`engine/src/program/generate.cpp:9050,9077,9189-9203`）。SYCL でも同様に自動 sizing 枝に含める（`engine/sycl/src/program/generate.cpp:4829,4851-4879`）。
- 明示的な `--expert-cache N` の場合、確認できた `owned_prefill_mib()` の利用先は multi-GPU 枝であり、指定 cache がプロンプトバッファと reserve に収まらないとき slot 数を削る。この枝では警告を出す（`engine/src/program/generate.cpp:9420-9435`、`engine/sycl/src/program/generate.cpp:4969-4985`）。単一 GPU の明示 cache はこの estimator の呼び出し条件ではない。
- `--prefill` が chunk を決め、`--no-prefill-borrow` と expert profile の有無が owned/borrowed 判定に関係する。`STRATA_OWNED_PRICE` による cache sizing 上の値の優先順位はなく、CLI は chunk/cache の設定を別途制御する（`engine/src/program/generate.cpp:3984-4008,4035,6821`）。

## 実行時の詳細

`owned_prefill_mib` は sizing 中に必要に応じて呼ばれる。chunk が正で prompt buffer が owned のときだけ static 初期化子が環境変数を読み、以後そのプロセス内で同じ `exact` 判定を使う。したがって初回の該当呼び出し後に環境を変更しても、この判定には反映されない。条件により呼ばれない場合は環境変数の読み取り自体が起きない（`engine/src/program/generate.cpp:9063-9067`、`engine/sycl/src/program/generate.cpp:4842-4846`）。

自動 cache sizing では見積もりを VRAM reserve に加え、空き VRAM から確保可能な expert slot 数を計算するため、`exact` は従来式より見積もりが小さくなる場合に cache slot を増やし得る。どれだけ変わるかはモデル状態・chunk・backend の `bytes_needed_owned` の計数に依存し、固定値ではない。multi-GPU の明示 cache sizing では同じ予約量を使って fit を計算し、指定 slot 数を超える場合に減らす（`engine/src/program/generate.cpp:9202-9203,9424-9435`、`engine/sycl/src/program/generate.cpp:4875-4879,4973-4985`）。

この変数は `--vram-reserve-mib` を置き換えず、独立に計算された owned-buffer 見積もりが reserve に加算される。`pf_borrow` が true なら `owned_prefill_mib` は常に 0 を返し、`STRATA_OWNED_PRICE` はその経路の見積もりに影響しない（`engine/src/program/generate.cpp:6815-6821,9202`、`engine/sycl/src/program/generate.cpp:4842-4845,4875`）。

## ログと測定値

`exact` 判定で見積もりを計算したときだけ stderr に次の形式の行を出す。chunk、`bytes_needed_owned` 由来の切り上げ MiB、従来式の MiB を表示する（`engine/src/program/generate.cpp:9067-9069`、SYCL は `engine/sycl/src/program/generate.cpp:4846-4848`）。

```text
strata generate: STRATA_OWNED_PRICE=exact: the prompt path's own buffers for a <chunk>-token chunk: <mib> MiB (the 0.1.39 rule: <old_mib> MiB)
```

条件を満たさない場合、または値が `exact` と完全一致しない場合、この変数に関する行は出ない。従来式で算出した値そのものはログ出力しない。cache sizing が不足した場合には別途 cache 容量に関する警告・エラー経路があるが、`STRATA_OWNED_PRICE` 固有の失敗や終了処理は実装されていない（`engine/src/program/generate.cpp:9411-9418,9430-9435`、`engine/sycl/src/program/generate.cpp:4954-4967,4978-4985`）。

## 根拠

- 候補名の全ソース参照と読み取り: `engine/src/program/generate.cpp:9063-9069`、`engine/sycl/src/program/generate.cpp:4842-4848`。
- cache sizing と適用条件: `engine/src/program/generate.cpp:6815-6821,9077-9078,9189-9203,9420-9435`、`engine/sycl/src/program/generate.cpp:4851-4879,4969-4985`。
- CLI での cache/chunk 設定: `engine/src/program/generate.cpp:3984-4008,4035`。
- owned buffer の計数処理: `engine/src/prefill/prefill.cpp:3713-3725`、`engine/sycl/src/prefill/prefill.cpp:2418-2431`。
