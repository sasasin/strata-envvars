# `STRATA_Q36_CKPT_EVERY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 エンジンがセッションごとに保存する GDN（recurrent / SSM）状態チェックポイントの間隔をトークン数で指定する。チェックポイントには各 GDN 層の convolution state と `S`、その位置の `hlast` が含まれ、ホストの pinned memory に保存される。後続リクエストのプロンプトが保持済みセッションの途中で分岐したとき、共通 prefix 以下のチェックポイントから再開できるため、分岐位置より前の GDN 計算をやり直さずに済む。値はトークン生成アルゴリズムや sampling の設定ではない。実装は `engine/src/qwen35/q36_engine.cu` の `Engine::init`、`ckpt_maybe`、`Serve::resume_len` にある（同ファイル: 1687-1692, 2233, 2317-2325, 4972-4985）。

## 値と判定

`Engine::init` が呼ばれるたび、共通 lambda `envn` が `std::getenv` で読み、`std::strtoll(..., 10)` で変換する。未設定または空文字は既定値 `4096`。変換で数字を1文字も消費しない文字列も既定値に戻る。変換後は `std::max<long long>(1, value)` が適用されるため、0・負数はすべて `1` になる。`strtoll` の end pointer が入力末尾かどうかは検査しないので、数値の後ろの文字は無視される。先頭空白と符号は `strtoll` の10進変換規則で扱われる。大文字小文字の概念はない。変換エラー（範囲外）を示す `errno` も検査せず、`strtoll` の返却値を上記 clamp に渡す（`engine/src/qwen35/q36_engine.cu:2224-2233`）。

| 入力例 | `envn` の結果 | `ckpt_every` |
|---|---:|---:|
| 未設定、空文字 | 4096 | 4096 |
| `4096` | 4096 | 4096 |
| `1`、`0`、`-7` | 入力の数値（または負値） | 1 以上に clamp。0 と負値は 1 |
| `12junk`、` 12tail`、`+12` | 12 | 12 |
| `true`、`junk12` | 数字を読めず既定値 | 4096 |
| `9223372036854775808` など範囲外 | `strtoll` の範囲エラー時返却値（`errno` は未確認） | 正の overflow は通常 `LLONG_MAX`、負の overflow は 1 へ clamp |

CLI 引数や設定ファイルによる上書きはこの読み取り経路にはない。別の環境変数 `STRATA_Q36_CKPT_N` はリングの深さを制御し、間隔の値を上書きしない。`STRATA_Q36_CKPT_N` も同じ `envn` で読み、既定値4、0未満を0に clamp する（同ファイル: 2232-2233）。

## 有効になる条件

- Qwen3.6 (`qwen35moe`) 用エンジン経路が使われること。ビルドでは `strata` がこのモデル family を `strata_qwen35` に切り替え、専用 `strata-q36` も同じエンジンを使う。`STRATA_HIP_GFX906` ビルドではこのエンジンが構成されない（`engine/cmake/strata_gpu_engine.cmake:565-582`）。SYCL は別プロジェクトで、この CUDA/HIP ソースを含まない（`engine/CMakeLists.txt:20-31`）。
- `STRATA_Q36_CKPT_N` が正数であること。0ならチェックポイント保存機能は無効で、プロンプト再利用は従来どおり保持セッション全体が次プロンプトの厳密な prefix の場合に限られる（同ファイル: 2232, 2296-2298, 4972-4985）。
- Qwen3.6 モデルに GDN 層があり、計算された `ckpt_bytes` が0でないこと。チェックポイント対象の層は `!L.attn` で数える（同ファイル: 2234-2241）。
- セッションが warmup 中でないこと。`ckpt_maybe` は warmup 中の保存をスキップする（同ファイル: 2318-2324）。

この変数単独を有効・無効にする真偽値判定はない。値は正の間隔へ変換されるが、上記条件を満たさなければチェックポイントは保存されない。

## 実行時の詳細

間隔はモデルロード後、`Engine::init` の初期化時に一度読み、`Engine::ckpt_every` に保持する。プロセス中に環境変数を変えても、初期化済みエンジンには反映されない。エンジンを再初期化すれば、その時点の値が読まれる（同ファイル: 1962-1968, 2224-2233, 5522）。

各セッションは最大 `STRATA_Q36_CKPT_N` 個のチェックポイントをリングで保持する。decode の1ステップ、prompt の各 chunk、speculative step の後に現在位置 `pos` で保存要否を確認する。`k = pos / ckpt_every` がそのセッションの最後の保存時の quotient より大きければ、現在位置の状態を保存する。したがって保存位置は処理境界であり、必ず interval の正確な倍数とは限らない。また初回は `ckpt_last_k == -1` のため、warmup 後の最初の `pos > 0` の処理境界で保存される（同ファイル: 1762-1764, 2317-2325, 3713-3717, 3737-3741, 4014-4019）。

保存時は GDN 各層の `conv` と `S`、`hlast` を device から pinned host memory へ非同期コピーし、stream を同期してから位置を記録する。リングの空き枠が必要なら pinned memory を割り当てる。CUDA host allocation や copy/sync の失敗は `CK` 経由で stderr にエラーを書き、プロセスを終了コード1で終了する（同ファイル: 82-89, 1720-1735, 2294-2315）。

次のリクエストでは、保持した token と画像の一致 prefix を求め、保持状態の末尾より手前で分岐した場合にその prefix 以下で最も新しいチェックポイントを選ぶ。位置が見つからない場合はセッションを reset してプロンプトを読み直す。見つかれば `conv`、`S`、`hlast` と rotary offset を復元し、それより後ろのチェックポイントを無効化して、保持 token をその位置まで切り詰める。attention K/V は prefix の位置に残る（同ファイル: 2280-2285, 2326-2353, 4972-4985, 5110-5128）。

## ログと測定値

`STRATA_Q36_CKPT_N > 0` かつチェックポイントサイズが正の場合、初期化時に stderr へ `strata-q36: GDN checkpoints: ... every %lld tokens; ...` の行を出す。出力される間隔は clamp 後の値。深さが0、またはサイズが0ならこのログは出ない（`engine/src/qwen35/q36_engine.cu:2234-2247`）。この環境変数に固有の無効値警告や fallback ログはない。測定値は該当資料にない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1687-1692` — チェックポイントの目的と GDN 状態。
- `engine/src/qwen35/q36_engine.cu:2224-2247` — 環境変数変換、clamp、サイズ計算、初期化ログ。
- `engine/src/qwen35/q36_engine.cu:2294-2325` — pinned memory への保存と interval 判定。
- `engine/src/qwen35/q36_engine.cu:2326-2353` — チェックポイント復元と後続 checkpoint の無効化。
- `engine/src/qwen35/q36_engine.cu:3713-3741, 4014-4019` — decode、prompt、speculative step からの保存確認。
- `engine/src/qwen35/q36_engine.cu:4972-4985, 5110-5128` — prefix 再開位置の選択と request 時の復元。
- `engine/cmake/strata_gpu_engine.cmake:565-582` — Qwen3.6 エンジンの family/build 条件。

`docs/SETTINGS.md:270` はこの変数の型を `on / off` と記載しているが、実装はトークン間隔を整数変換して1以上に clamp する。したがって同表の型分類は実装と一致しない。
