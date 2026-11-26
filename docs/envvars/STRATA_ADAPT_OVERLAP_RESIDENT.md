# `STRATA_ADAPT_OVERLAP_RESIDENT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_ADAPT_OVERLAP_RESIDENT=1` は、resident RAM mode のときに adaptive overlap を止める既定の条件を解除します。この変数だけでは overlap を起動しません。別の opt-in `STRATA_ADAPT_OVERLAP` が有効で、ほかの実行条件も通った場合に、adaptive tier の swap コピーを次の decode window と重ねられます。判定は `engine/src/program/generate.cpp` の serve 初期化中、`aov_why` の理由判定で行われます（`engine/src/program/generate.cpp:15113-15136`）。

## 値と判定

コードは環境変数全体を parse せず、`getenv` が非 null で、値の先頭文字が `'1'` かを直接確認します（`engine/src/program/generate.cpp:15132-15134`）。

| resident RAM mode | 値 | resident mode による停止理由を解除するか |
|---|---|---|
| あり | 未設定 | いいえ |
| あり | 空文字 | いいえ（先頭文字は `\0`） |
| あり | `1`、`10`、`1anything` | はい（先頭文字だけを見る） |
| あり | `0`、`true`、` 1`、`-1`、`01` | いいえ |
| なし | 任意 | この判定は適用されず、変数は実行条件に影響しない |

数値変換、空白除去、大文字小文字変換、末尾の検査、範囲チェックはありません。空文字を含む設定値は「先頭が `1`」でなければ無効です。無効値に対する警告やエラーはありません。

## 有効になる条件

- serve の adaptive overlap 判定で `src.complement_ready()` が真、つまり resident RAM copy が利用可能な場合にだけ、この変数が resident mode の拒否条件を解除します。resident RAM mode は GPU cache にない expert を RAM に置き、GPU cache との adaptive swap の対象にする経路です（`engine/src/program/generate.cpp:11747-11756`, `12196-12202`）。resident RAM mode が動いていない場合、この変数は不要です。
- overlap 自体を要求する `STRATA_ADAPT_OVERLAP` が別途先頭文字 `1` である必要があります。これは `adapt_overlap()` が static local に読み、先頭文字のみで判定します（`engine/src/program/generate.cpp:2269-2288`, `15122`）。この変数はその opt-in を上書きしません。
- 次の条件も必要です。これらは `aov_why` の優先順で判定され、満たさないときは最初の理由が採用されます（`engine/src/program/generate.cpp:15122-15136`）。
  - multi-GPU / layer split でない。
  - `--remote-expert-opt`、`--adapt-async`、`--pipeline-windows` を使わない。
  - page-locked swap sources (`pin_blobs_on()`) が無効。これは HIP / `STRATA_HIP_GFX906` の非 Windows build で `STRATA_ARENA_MMAP` の先頭文字が `1` のときだけ blocker になります（`engine/src/program/generate.cpp:595-601`）。
  - `STRATA_DMA_BATCH` の mode が 0。空または未設定は既定値 0、空でない値は `atoi` で変換され、変換後が非 0 なら blocker です（`engine/include/strata/core/dma_batch.hpp:28-35`）。
  - `STRATA_ADAPT_LAG` の parse 結果が 1（未設定は 1、設定時は `max(1, atoi(value))`）で、`STRATA_ADAPT_NOWAIT` の先頭文字が `1` ではない（`engine/src/program/generate.cpp:2237-2250`）。
  - adaptive tier が動作する（`drive.d.usage` が空でない。通常は `--adapt-every` と `--adapt-swaps` が有効な状態）。
- 条件を通った後も `ver.set_adapt_gate(&agate)` が成功する必要があります。`STRATA_VERIFY_DEVICE_PLAN` による device-planned layers が有効なら gate を設定できず、この overlap は使われません（`engine/src/program/generate.cpp:15137-15144`）。
- 条件を通るかの判定後、`STRATA_ADAPT_SIGNAL` の値に従って layer copy 完了の通知方法を選びます。これはこの環境変数の有効条件そのものではありませんが、overlap の実行準備に関係します（`engine/src/program/generate.cpp:15144-15170`）。
- `--serve` の server decode 初期化・window 処理で判定される値です。通常の単発 CLI 経路や別プロセスへ設定を書き出す処理は見つかりません（`engine/src/program/generate.cpp:15113-15122`, `22819-22835`）。

## 実行時の詳細

変数は serve 初期化時の `aov_why` 評価で、その場で2回 `std::getenv` を呼び、static cache には保存しません（`engine/src/program/generate.cpp:15122-15136`）。ただし結果の `aov` は初期化時に決まり、後の decode window はその値を使います。したがってサーバープロセス実行中に環境を変更しても、この server session の overlap 判定には反映されません（`engine/src/program/generate.cpp:15176-15186`, `22819-22835`）。

overlap が有効になると、pending swap の residency table を window 前に反映し、各 layer のコピーが着地するまでその layer の verify 計画を gate で待たせます。resident RAM mode では `soft_commit_exchanges()` を使い、RAM copy 側の場所はコピー完了まで維持します。`soft_commit_exchanges()` が失敗した場合は通常の待機付き `apply_pending(true)` に戻ります（`engine/src/program/generate.cpp:22819-22835`）。

## ログと測定値

- overlap が有効なら stderr に `strata serve: adaptive overlap (STRATA_ADAPT_OVERLAP=0 turns it off): ...` が出ます。実行終了時には overlap が処理した window 数と layer wait 合計の `strata decode adapt overlap: ...` も出ます（`engine/src/program/generate.cpp:15176-15181`, `23382-23384`）。
- overlap の要求があり、resident RAM mode がこの変数の未設定・無効値で拒否された場合は `strata serve: STRATA_ADAPT_OVERLAP=1 is off: not in the resident RAM mode unless STRATA_ADAPT_OVERLAP_RESIDENT=1` が出ます（`engine/src/program/generate.cpp:15130-15135`, `15182-15183`）。先行する別条件に当たる場合は、その条件の理由が表示されます。
- `STRATA_ADAPT_OVERLAP` 自体が要求されていない場合は `strata serve: adaptive overlap: off...` が出て、resident 例外が通っても有効化されません（`engine/src/program/generate.cpp:15122`, `15184-15186`）。
- ソースコメントは resident RAM mode での overlap の結果として RTX A4000 `+7.0% (5/5 pairs)`、RTX 3060 `-2.6% (0/5)` と記しますが、モデルや実行設定などはそのコメントに記載されていません。これはコードコメント上の限定的な報告で、一般的な性能値とは扱えません（`engine/src/program/generate.cpp:15130-15131`）。`docs/DETAILS.md` は `STRATA_ADAPT_OVERLAP` の一般条件・別構成での測定を説明していますが、この resident 例外変数の記載はありません（`docs/DETAILS.md:1260`, `1720`）。

## 根拠

- `engine/src/program/generate.cpp:15113-15136` — overlap の起動判定、resident RAM 例外、他の拒否条件。
- `engine/src/program/generate.cpp:15137-15186` — gate 準備、ログ、無効理由。
- `engine/src/program/generate.cpp:22819-22835` — window ごとの pending swap 適用と resident RAM の soft commit。
- `engine/src/program/generate.cpp:11747-11756`, `12196-12202` — resident RAM mode と adaptive swap の説明・状態ログ。
- `engine/src/program/generate.cpp:23382-23384` — overlap の実行結果ログ。
