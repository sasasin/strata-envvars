# `OWN5_NOISE_DIR`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

これは配布版 Strata の通常設定ではなく、画像生成ゲート用のテストフックが適用された `sd-cli` のノイズ入力元を差し替える環境変数である。`stage_hooks.py` が stable-diffusion.cpp のコピーに挿入する `PhiloxRNG::randn` の処理で読み、未設定時の Philox RNG の結果の代わりに、seed ごとの float32 ノイズファイルを返す。テスト用コピー以外にこの読み取りはない（`terminal/tools/image/gate/stage_hooks.py:1-10,88-99,118-125`）。

## 値と判定

挿入コードは `std::getenv` のポインタ有無だけで分岐し、空文字判定や値の parse はしない。unset なら既存の `randn` 実装へ続き、設定済みなら値をディレクトリ文字列として使う。空文字も設定済みとして扱われ、パスは `/noise_<seed>.bin` になる。大文字小文字、空白、数値としての妥当性は検査しない（`terminal/tools/image/gate/stage_hooks.py:88-99`）。

| 条件 | unset | 設定時にファイルを読む値 | 失敗する値・状態 |
|---|---|---|---|
| `stage_hooks.py` で加工した `sd-cli` | 元の `randn` 処理へ進む | 任意の非 null 文字列。`<値>/noise_<seed>.bin` を開く | ファイルが開けない、または必要な float 数 `n` 個を読めない場合は abort。空文字も分岐に入り `/noise_<seed>.bin` を試す |

ファイルから `n` 個の `float` を読み、要素数が一致すれば返す。読み込んだ float の有限性・値域・ファイルの余剰バイトや配列形状は検証しない。`n` 個より短い場合（ファイルを開けない場合を含む）は失敗する（`terminal/tools/image/gate/stage_hooks.py:89-98`）。

## 有効になる条件

- `stage_hooks.py` が対象ツリーの `src/core/rng_philox.hpp` にフックを挿入し、そのツリーから作ったバイナリを実行する必要がある。これは OWN-5 テスト専用で、文書の説明では出荷ビルド経路には含まれない（`terminal/tools/image/gate/stage_hooks.py:1-2,118-125`）。
- `build_variant.py` は通常、`stage_hooks.py` を適用したコピーを作る。一方 `--noise` を指定した分岐は Strata の `sdcpp_noise/apply.py` を適用し、stage hooks を使わない。この分岐でこの変数が処理される根拠はない（`terminal/tools/image/gate/build_variant.py:1-9,22-30`）。
- `run_set.py --noise-from DIR` は各 `sd-cli` 子プロセス用の環境に `OWN5_NOISE_DIR` を設定する。`--env OWN5_NOISE_DIR=...` でも環境に渡せるが、両方を指定した場合は後段の `--noise-from` が上書きする。`--noise-from` を省略した場合はベース環境から継承した値が残る（`terminal/tools/image/gate/run_set.py:102-108,127-149`）。
- `sd-cli` 側がフックを通る呼び出しでのみ参照される。`run_set.py` は seed をジョブに設定し、その seed が作るファイル名に使われる。画像設定の `noise: "strata"` は別の生成器選択であり、この変数の有効化条件ではない（`terminal/tools/image/gate/run_set.py:114,127-149`; `terminal/serve/images.py:149-174`）。

## 実行時の詳細

`run_set.py` は `IM.image_env(cfg)` から環境を作り、`--env` の値を加え、各画像ジョブの環境を複製する。`--noise-from` があれば `Path(...).expanduser()` した文字列を設定し、その `env` を `subprocess.Popen` に渡す。`stage_hooks.py` が挿入する C++ は `randn` 呼び出しごとに `getenv` を行うため static cache はない。プロセス内で環境値が変更されれば次の呼び出しで再取得されるが、この経路には変更処理はない（`terminal/tools/image/gate/run_set.py:102-108,110-149`; `terminal/tools/image/gate/stage_hooks.py:88-99`）。

ファイルを必要数読めると RNG の `offset` を 1 増やし、そのベクトルを返す。ファイルの欠落・短さでは stderr に `OWN5: noise file <path> missing or short` を出して `std::abort()` する。`run_set.py` は子プロセスの stdout と stderr をまとめてログファイルへ保存し、終了コードと末尾のログ行を結果 JSONL に記録する（`terminal/tools/image/gate/stage_hooks.py:92-98`; `terminal/tools/image/gate/run_set.py:146-179`）。

## ログと測定値

ファイルを読み込めた場合の成功ログはない。読み込み不足時の実装上の stderr は `OWN5: noise file %s missing or short\n` で、その後 abort する。`run_set.py` の記録では該当子プロセスの終了コードが `rc`、末尾 8 行までのログが `error` に入る（`terminal/tools/image/gate/stage_hooks.py:95`; `terminal/tools/image/gate/run_set.py:146-179`）。この環境変数に関する測定値は資料にない。

## 根拠

- `terminal/tools/image/gate/stage_hooks.py:1-10,88-99,118-125` — テスト専用フックの適用範囲、`getenv` 判定、seed 名のファイル読込、失敗処理。
- `terminal/tools/image/gate/build_variant.py:1-9,22-30` — stage-hooks ビルドと Strata noise ビルドの分岐。
- `terminal/tools/image/gate/run_set.py:102-108,110-149,154-179` — 環境値の継承・設定・子プロセスへの転送とログ・終了結果の記録。
- `terminal/serve/images.py:149-174` — `noise: "strata"` が別途 `strata_noise=1` を渡す実装。
