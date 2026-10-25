# `--pipeline-windows`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | CMake で生成するネイティブ `strata` 推論エンジン |
| オプション | `--pipeline-windows` |
| 別名 | なし |
| 値 | 整数 `N`。実効値は `0`、`1`、`2` の範囲 |

## 役割

`--serve` と複数 GPU の layer split で、隣り合う verify window を GPU stage 間で重ねて処理します。`1` は対応する prompt の短い読み込みだけ、`2` はそれに加えて decode window も投機的に重ねます。どちらも条件を満たさなければ無効化されることがあります。parser と実行時の適用判定は `src/program/generate.cpp:767-772, 2671, 4238-4288` にあります。

## 使い方

既存の layer split と MTP drafter を使う `strata serve` の起動例です。

```sh
strata --serve --pack /path/to/pack --tokens "1,2,3" --layer-split 20 --mtp /path/to/drafter --spec 4 --pipeline-windows 2
```

エンジンの usage は `--pack` と `--tokens` を含む呼び出し形式、および `--serve` と layer split での使用を示しています（`src/program/generate.cpp:806-812, 917-920`）。`--layer-split` の指定形式やモデルの配置条件はこのオプション文書の対象外です。

## 値と既定値

- parser は `atoi` で整数変換後、`0..2` に clamp します。したがって負数は `0`、`2` より大きい数は `2` になります。整数として読めない値は `atoi` により `0` 相当です。複数回指定した場合は parser が順に代入するため最後の値が残ります（`src/program/generate.cpp:2416-2421, 2671`）。
- 値を省略すると parser の共通処理が `--pipeline-windows needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。
- 省略時の内部値は `-1`（自動判定）です。HIP build では `STRATA_PIPELINE_AUTO` が `0` でなく、`--serve`、異なる GPU を使う layer split、stage 数、MTP (`--mtp` と `--spec >= 2`) を含む条件を満たし、helper cache・batch slots・peer device・async adaptation が使われていなければ自動有効化の候補になります。GPU architecture が gfx12 WMMA であることも必要です。既定の最小 stage 数は通常 3、MTP drafter を最初の GPU に置く設定が既定で有効なら 2 です。`STRATA_PIPELINE_AUTO_MIN_STAGES` は最小値を上書きしますが、値は少なくとも 2 に補正されます（`src/program/generate.cpp:1956-1967, 4246-4268`）。
- 明示値 `0` は自動判定を上書きして無効にします。明示値 `1` / `2` は自動判定に依存せず、以下の適用条件で検査されます（`src/program/generate.cpp:2671, 4253-4273`）。

## 実行時の動作

- 値 `1` は、2 stage の layer split で `read_windows_pl` を使い、stage 0 が次の window を処理している間に stage 1 が現在の window を処理します。適用時は prompt verify window の hand-off と stage ごとの stream を使います（`src/program/generate.cpp:8987-9012, 13105-13110, 13194-13199`）。3 stage 以上で明示した `1` はサポートされず、無効化されます。
- 値 `2` は prompt の重ね合わせに加え、decode でも stage 0 が次の window を投機実行し、最後の stage が現 window を検証します。予測が外れた場合は front stage の GDN state を snapshot から戻し、確定 token で処理を進めます。適用には MTP drafter と `--spec >= 2` が必要です（`src/program/generate.cpp:767-772, 9237-9254, 14223-14242`）。
- 2 stage の明示値 `2` では、drafter を最初の GPU に置けない場合も指定自体は維持され、共有 GPU 上での競合について stderr に注意が出ます。自動有効化では同条件なら通常 3 stage 以上が必要です（`src/program/generate.cpp:4246-4264, 4289-4300, 4403-4411`）。
- second verifier などの追加領域は expert cache のサイズ決定時に予約されます。値が正なら各 GPU の expert cache から約 160 MiB を除き、値 `2` では先頭 stage の GDN snapshot 領域も見積もりに加えます（`src/program/generate.cpp:4505-4518, 6021-6027`）。

## 適用条件と副作用

有効にするには `--serve`、異なる GPU にまたがる 2 stage 以上の layer split、MTP drafter (`--mtp`) と `--spec >= 2` が必要です。`--batch` slots、`--peer-device`、helper cache (`--expert-cache-device1..3` / `--remote-expert-opt`) とは併用できません。3 stage 以上で `--adapt-async` と値 `2` を明示した場合も pipeline 側が無効になります。これらの条件を満たさない明示値は stderr に理由を出して `0` に変更し、起動を続けます（`src/program/generate.cpp:4273-4288`）。

追加 verifier や hand-off、stream、値 `2` の GDN snapshot と drafter row buffer を GPU/host memory に確保します。stream または hand-off の作成、second verifier / row buffer の確保に失敗すると `strata serve` はエラーを stderr に出して終了コード `1` で終了します（`src/program/generate.cpp:9000-9007, 9112-9159`）。値 `2` の GDN snapshot が確保できない場合は decode の重ね合わせをやめて serial decode に戻します。prompt 側の pipeline 判定は別に行われます（`src/program/generate.cpp:9251-9289, 14231-14242`）。

`--pipeline-windows` の pipeline が有効な場合、`STRATA_SPLIT_OVERLAP` による別の stage overlap は併用せず、その旨を stderr に出します（`src/program/generate.cpp:9030-9041`）。値 `2` でも repetition penalty (`penalty_last_n`) を使う request と coupled draft sampling は decode を serial にします（`src/program/generate.cpp:14231-14240`）。

## 出力とエラー

- 自動有効化時は stderr に既定で有効になった旨、実際に pipeline を組んだ場合は値と stage 数を出します（`src/program/generate.cpp:4268-4271, 9285-9289`）。
- 対応外の明示値は無効化理由を stderr に出しますが、その理由だけでは起動失敗になりません（`src/program/generate.cpp:4273-4288`）。
- 値 `2` の GDN snapshot が確保できない場合は serial decode へ切り替える旨を stderr に出します（`src/program/generate.cpp:9264-9270`）。pipeline 実行中の準備失敗は `ERR <理由>` を stdout に出し終了コード `1` になります（`src/program/generate.cpp:14242-14246`）。
- 調査した source では、このオプション単独の通常完了時に必ず出す stdout メッセージは確認できません。prompt pipeline の進捗出力 `PP ...` は処理経路内にあります（`src/program/generate.cpp:13185-13191`）。

## 根拠

- parser・既定値・usage: `src/program/generate.cpp:767-772, 917-920, 2418-2421, 2671`。
- 自動選択と適用可否: `src/program/generate.cpp:1956-1967, 4246-4300`。
- メモリ見積もりと verifier / stream 初期化: `src/program/generate.cpp:4505-4518, 6021-6027, 8987-9012, 9112-9159, 9251-9289`。
- prompt / decode の使用箇所と request 単位の serial fallback: `src/program/generate.cpp:13105-13110, 13194-13199, 14223-14246`。
- 利用者向け説明: `docs/MULTI_GPU.md:427-499`。同文書は `1` と `2` の動作、メモリ負担、無効条件を説明しています。usage の「two GPUs」という記載 (`src/program/generate.cpp:917`) は概要で、ソース上は3 stage 以上でも値 `2` が適用されます。

この調査では指定 revision のソースと checkout 内文書を確認しました。Release 配布物や、各 GPU / model / backend 上での実行結果は確認していません。`--help` の実機出力も実行していません。
