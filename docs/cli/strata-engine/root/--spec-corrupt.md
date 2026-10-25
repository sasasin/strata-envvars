# `--spec-corrupt`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数。Terminal CLI とは別） |
| オプション | `--spec-corrupt` |
| 別名 | なし |
| 値 | 整数 `N`。parser は `std::atoi` で変換する |

## 役割

投機的デコードの検証用オプションです。`N > 0` の場合、verify window に入れる draft のうち、通算で N 個ごとの draft token を意図的に別の token ID に置き換えます。draft の誤りを含む窓を verifier がどう処理するかを確認する用途です。通常の利用者向け生成で正確さや品質を改善する設定ではありません。

## 使い方

```sh
strata --pack MODEL.gguf --tokens 1,2,3 --mtp MTP_DIR --spec 4 --spec-corrupt 3
```

これは `--spec 4` で投機的デコードを有効にした実行例です。モデル・token ID・MTP の実際のパスや対応形式は利用環境に合わせてください。

## 値と既定値

- 省略時は `0` です。この値では token を置換しません（`src/program/generate.cpp:672`）。
- `N > 0` なら draft token を作るたびにカウンターを進め、N 個ごとの draft を `(d + 1) % n_vocab` にします。これは語彙 ID の範囲内で元と異なる ID になります（`src/program/generate.cpp:16425, 16592-16599`）。
- `0`、負数、数値として読めない文字列は `atoi` の変換結果が正でない限り置換を発生させません。専用の範囲検証はありません。数値の前置部分を読める場合は `atoi` の変換規則に従います（`src/program/generate.cpp:2620`）。
- 同じオプションを複数回指定すると、parser が `Options` の値を順に代入するため最後の値が使われます（`src/program/generate.cpp:2416-2421, 2620`）。

## 実行時の動作

この値は speculative loop の verify window 構築時に使われます。window の先頭 token は置換対象外で、後続 draft token ごとにカウンターが進みます。MTP draft、suffix draft、lookup-chain draft、oracle から来る draft も、window に組み込まれた位置では同じ置換処理を通ります（`src/program/generate.cpp:16591-16599`）。

適用には speculative loop が実行され、少なくとも一つの draft token が窓に入る必要があります。したがって `--spec-corrupt` 単独では効果がなく、`--spec` や利用する draft source などの条件を満たす実行が必要です。投機的デコードの入口と oracle/follow ファイル読込エラーは `src/program/generate.cpp:16095-16124` にあります。

`N > 0` のとき、MTP の確率分布を verifier に設定する経路も止まります。`ver.set_spec_q(...)` の条件に `o.spec_corrupt <= 0` が含まれています（`src/program/generate.cpp:16608`）。

## 適用条件と副作用

- オプションの parser は engine 共通引数列にありますが、確認した CUDA/HIP `src/program/generate.cpp` では置換処理は通常の speculative loop にあり、`--serve` のリクエスト処理とは別です（parser: `src/program/generate.cpp:2619-2621`、serve 分岐: `src/program/generate.cpp:8354-8365`、通常 loop: `src/program/generate.cpp:16095-16102, 16591-16599`）。
- 置換されるのは verifier に渡す仮 draft token です。実際に採用される生成 token は verify の結果に従います。したがって出力を意図的に壊す指定ではなく、誤った draft を含むケースを作る指定です。
- SYCL 実装にも同じ既定値・`atoi` parser・置換処理があります（`sycl/src/program/generate.cpp:633, 1918, 12707-12714`）。ここでは実行環境ごとの挙動差や実機での動作は検証していません。

## 出力とエラー

- `--spec-corrupt` の値自体に対する専用の警告・validation error はありません。
- 値を省略すると `next()` が標準エラーに `--spec-corrupt needs a value` を出して終了コード `2` で終了します（`src/program/generate.cpp:2418-2420, 2620`）。
- 未知の引数は標準エラーに `unknown argument: ...` と usage を出して終了コード `2` です（`src/program/generate.cpp:2787-2792`）。
- speculative loop が正常終了すると、標準出力に `speculation` の rounds・accepted drafts 数などを表示します。破損させた token ID 自体を記録する出力は確認できません（`src/program/generate.cpp:16725-16733`）。verify 実行失敗時は標準エラーにエラー内容を出し、終了コード `1` で終了します（`src/program/generate.cpp:16609-16620`）。

## 根拠

- 索引上の配置と scope: `docs/cli/README.md:1128-1134, 1283-1287`（調査対象リポジトリ外の文書）。
- parser、既定値、置換処理、確率分布の条件: `src/program/generate.cpp:652-672, 2416-2421, 2620, 16425, 16591-16620`。
- speculative loop の入口および出力: `src/program/generate.cpp:16095-16124, 16725-16733`。
- SYCL の対応処理: `sycl/src/program/generate.cpp:619-633, 1918, 12707-12714`。

調査は上記 commit の parser とコード経路に限定しました。CLI バイナリの help、GPU 実行、性能、Release 配布物は確認していません。
