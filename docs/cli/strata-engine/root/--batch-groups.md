# `--batch-groups`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、トップレベル） |
| オプション | `--batch-groups` |
| 別名 | なし |
| 値 | `G`（整数）または CUDA/HIP parser では `auto` |

## 役割

`--batch` で作る複数の会話 slot を G グループに分け、層分割（`--layer-split`）した GPU 間でパイプライン実行する数を指定します。グループ数が 1 の場合は slot 全体を一つの window として各 GPU stage を順番に通します。G が 2 以上の場合、stage k があるグループを処理する間に stage k+1 が別グループを処理します（`src/program/generate.cpp:665-669,11739-11748`）。

## 使い方

複数 GPU の層分割で、8 slot を4グループに分ける例です。`--batch-groups 4` が有効になるには `--batch` が4で割り切れる必要があります。

```sh
strata --serve --layer-split 12,24,36 --expert-profile /path/to/profile.json \
  --batch 8 --batch-groups 4
```

GPU ごとの stage 分割と serving が前提です。実行ファイルは CMake が生成する推論エンジンで、Terminal CLI の `strata serve` とは別の parser です（索引: `docs/cli/README.md:1128-1143`）。

## 値と既定値

- **CUDA/HIP parser**: 数値は `std::atoi` で整数化され、`auto` は専用フラグとして認識されます。オプション自体の数値範囲 validation はありません。値の省略は parser 共通の `--batch-groups needs a value` を stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2421,2612-2617`）。
- **`G=1`**: パイプラインを使わず、全 slot を順次処理する指定です。`G` が 0、負数、または整数として解釈できない文字列も parser では拒否されず、`atoi` の結果が 1 以下なら同様にパイプライン分岐に入りません（`src/program/generate.cpp:2612-2617,11739-11748`）。明示的な検証エラーにはなりません。
- **`G>1`**: slot 数を G グループに分けます。G が slot 数を割り切らない、または層分割がない場合、batch 有効時には警告を stderr に出して1グループへ戻します。slot 数が VRAM などの都合で縮小された後に割り切れなくなった場合も、最終的に1グループへ戻ります（`src/program/generate.cpp:5380-5385,5427-5436`）。
- **`auto`（CUDA/HIP）**: 層分割の stage 数を超えず、batch slot 数を割り切る最大のグループ数を選びます。明示指定がなくても、層分割があり `--batch` が2以上なら自動選択が既定です。層分割なし、または batch が1以下の場合は既定1です（`include/strata/program/batch_groups.hpp:41-67`）。
- **SYCL parser**: `--batch-groups` は `atoi` のみで処理され、`auto` を特別扱いせず暗黙の auto 既定もありません。したがって `auto` は整数0として扱われ、1以下と同じくパイプラインになりません（`sycl/src/program/generate.cpp:1915,4099-4103,9248-9251`）。SYCL 向けのヘルプも単に `G` と表示します（同 `:835`）。

## 実行時の動作

CUDA/HIP 版の自動選択は、stage 数を `stages.size()+1` GPU として数え、2からその数および slot 数までを調べ、slot 数を割り切る最大値を使います（`include/strata/program/batch_groups.hpp:41-47`）。ただし、暗黙の既定 auto は次の場合に1へ変更されます。

- `--adapt-async 1` が有効で、明示的な `--batch-groups` がない場合。パイプライン経路では batch の adaptive tier が動作しないためです（`include/strata/program/batch_groups.hpp:59-65`, `src/program/generate.cpp:8066-8092`）。
- batch MTP が有効で、`STRATA_BATCH_MTP_SERIAL` が空でないかつ先頭文字が `0` ではない場合。明示的な `--batch-groups 1` も serial window を選べます（`src/program/generate.cpp:5299-5321`, `include/strata/program/batch_groups.hpp:59-65`）。
- 非 HIP ビルド（NVIDIA/CUDA 経路）で、ちょうど2 GPU の層分割、batch MTP 無効、adaptive async 無効の場合、`STRATA_BATCH_GROUPS_NV_SERIAL` が未設定または先頭文字が `0` 以外なら1グループにします。`STRATA_BATCH_GROUPS_NV_SERIAL=0` はこの暗黙の serial 選択を解除します。明示的な `--batch-groups auto` はこの暗黙既定の例外処理を受けず、自動グループ数を要求します（`src/program/generate.cpp:5293-5297`, `include/strata/program/batch_groups.hpp:54-65`）。

グループが2以上でパイプラインが有効になるのは、batch slot があり、複数の layer stage がある場合です。各 group は `batch / groups` slot を持ち、各 stage に対して verifier の batch launch を行います（`src/program/generate.cpp:11739-11767`）。起動時には選択グループ数を stderr に記録し、処理終了時には group 数・各 group の slot 数・window 数・行数・処理率を stderr に出します（同 `:5361-5378,11923-11930`）。

## 適用条件と副作用

- batch slot は `--serve` と2以上の `--batch` が必要で、層分割では各 stage が別 GPU 上にある必要があります。条件を満たさない `--batch` は警告を出して無効化されます（`src/program/generate.cpp:5340-5347`）。層分割自体も `--serve` を要求し、複数 GPU の分割には `--expert-profile` が必要です（同 `:2998-3027,3069-3072`）。
- batch slot ごとに各 stage 上の session state を追加確保します。起動時の VRAM 確保が失敗すると、確保できた slot 数に減らし、2 slot 未満しか確保できない場合は batch を無効化します。したがってグループ数は要求どおりでも slot 数が調整され得ます（`src/program/generate.cpp:5386-5440`）。
- パイプライン経路では slot ごとの MTP draft は実行しません。暗黙の既定でパイプラインが優先される場合は batch MTP が無効化され、明示的に groups>1 を指定した場合は `--batch-mtp` の draft が走らない旨の警告が出ます（`src/program/generate.cpp:5301-5321,11743-11748`）。
- `--adapt-async 1` はグループ数が2以上の経路と併用できず、batch 有効時には adaptive async が無効化されます（`src/program/generate.cpp:8066-8092`）。
- pipelined groups は slot ごとの verifier row を作り、stage 間で複数グループを進行させます。slot session が GPU VRAM を消費し、その分 expert cache に使える VRAM が減ります（`src/program/generate.cpp:5272-5275,5417-5440,11739-11805`）。
- `--batch-groups` は serving の batch 機能に関する指定です。通常の単発 generation や `--batch` が無効化された実行では、group 設定は実効しません（`src/program/generate.cpp:5340-5355,11739-11748`）。

## 出力とエラー

- 値なしは stderr に必要値を示し、終了コード2です（`src/program/generate.cpp:2418-2421`）。
- 未知の引数は stderr に `unknown argument` を出し、usage を表示して終了コード2です（`src/program/generate.cpp:2787-2792`）。
- groups>1 が層分割なし、または batch 数を割り切れない場合は警告を出して1グループへ fallback します。これは終了エラーではありません（`src/program/generate.cpp:5380-5385`）。
- パイプライン経路でも batch window の上限を超える状態が残る場合、stderr に理由を出して serving loop が false を返します（`src/program/generate.cpp:11748-11755`）。

## 根拠

- parser と help 表示: `src/program/generate.cpp:665-669,910-916,2418-2421,2612-2617`。
- auto と暗黙既定の計算: `include/strata/program/batch_groups.hpp:21-67`; 設定値の受け渡しと環境変数: `src/program/generate.cpp:5280-5297`。
- batch MTP との条件: `src/program/generate.cpp:5299-5321,11743-11748`。
- batch slot の validation・確保・縮小: `src/program/generate.cpp:5340-5440`。
- パイプライン処理と出力: `src/program/generate.cpp:11739-11930`。
- SYCL parser の挙動差: `sycl/src/program/generate.cpp:630,835,1915,4099-4103,9248-9260`。
- 利用者向け補助資料: `docs/BATCHING.md:88-96,426-433`。この説明表は2 GPU NVIDIA の serial 既定を「PROPOSED」と記していますが、調査対象 revision の parser 側では既定有効の条件が実装されています（`src/program/generate.cpp:5293-5295`, `include/strata/program/batch_groups.hpp:59-65`）。測定値や性能上の推奨は本書では保証しません。
