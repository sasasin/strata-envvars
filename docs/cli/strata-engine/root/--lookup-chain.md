# `--lookup-chain`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン、root 引数） |
| オプション | `--lookup-chain` |
| 別名 | なし |
| 値 | 整数 `K`。有効値は 0〜7。既定値 0（無効） |

## 役割

MTP が提案した draft の後ろに、文脈中の一致箇所から続きの token を最大 `K` 個追加提案する。提案は通常の verify window で検証されるため、このオプションは draft の作り方と窓幅を変える。実際に使うには MTP drafter が動作する speculative generation 経路が必要で、初回 window、既に suffix lookup から提案している window、または窓に空きがない場合は chained lookup を行わない。

## 使い方

```sh
strata model.strata --serve --mtp /path/to/mtp --spec 4 --lookup-chain 3
```

モデル、server 設定、その他の生成引数は利用環境に合わせる。`K=0` は機能を無効にする。

## 値と既定値

値は `std::atoi` で整数化し、`std::clamp(..., 0, 7)` で範囲に収める。したがって負数は 0、大きな値は 7 になる。整数として解釈されない文字列も `atoi` の結果により 0 となる。parser は独自の範囲エラーを返さず、値がない場合は stderr に `--lookup-chain needs a value` を出して終了コード 2 で終了する。既定値は 0。

`--lookup-chain-min M` は関連する別オプションで、連鎖 lookup が延長する最短一致長を指定する。値は少なくとも 3 に補正され、既定値も 3。これは本オプションの `K` とは別の設定である。

## 実行時の動作

起動時、`K>0` かつ `--spec >= 2` なら engine は `--spec` を MTP の基準として保持し、verify window の上限を `min(max(--spec, --mtp-max-t) + K, 8)` まで広げる（`--mtp-max-t` 未指定時は `--spec` が基準）。`--spec < 2` ではこの拡張処理は行われない。window 上限は実装の narrow verify 上限 8 に制限される。

生成中は MTP draft の末尾を含む直近最大 64 token を lookup source に渡し、最大 `min(K, window の残り)` token を求める。一致長が `--lookup-chain-min` 未満の候補は採用されない。組み込み prompt lookup と登録済み追加 source を照会し、最短一致長を満たす候補のうち一致長が最長の source を使う。同率なら先に照会された source が残る。候補 token は verify window に追加され、検証・受理された分だけ出力されるため、未検証の提案がそのまま出力される仕組みではない。

通常は `DraftPolicy` が一致長別の受理率と window の測定コストを使い、連鎖を追加したときの期待 token/ms が MTP window 単独より margin を超えて有利かを判定する。`STRATA_LOOKUP_CHAIN_FIXED` が設定されている場合、この連鎖長の policy gate を迂回して得られた候補を使う（ただし候補がない場合や他の適用条件は変わらない）。

## 適用条件と副作用

- `--lookup-chain` は MTP 自体を有効化しない。MTP drafter が有効な speculative 経路でのみ、MTP draft の後ろに連鎖を付ける。
- 連鎖窓の最大サイズは 8 token。すでに `--spec` や `--mtp-max-t` が大きい場合、上限に達して追加幅が `K` より小さくなることがある。
- `--lookup-max-t` が有効なときは、lookup 用に許可された window サイズと graph が利用可能かも適用される。`graph_fits` が失敗すると生成経路は `ERR ...` を出して失敗する。
- オプション有効時は prompt/output token 履歴を lookup drafter と追加 draft source に供給し、連鎖候補・受理数を記録する。ファイルの書き換えやネットワークアクセスは、このオプションの処理からは確認できない。

## 出力とエラー

server 経路では終了時に stderr へ `strata serve: lookup chain: ...` の窓数・提案数・受理数集計を出す。生成経路では stdout に `lookup chain` の同種集計を出す。欠落値は parser の stderr と終了コード 2 で失敗する。verify window の上限を超える組合せは後続 validation で `--spec ...: a speculative window holds 2..N tokens` を stderr に出し、終了コード 1 となる場合がある。

## 根拠

- `engine/src/program/generate.cpp:1161-1165` — engine option 状態と初期値。
- `engine/src/program/generate.cpp:1351-1354` — help の説明。補助資料として parser 定義と照合。
- `engine/src/program/generate.cpp:3839-3841` — 値欠落時の stderr と終了コード。
- `engine/src/program/generate.cpp:4120-4121` — `--lookup-chain` と `--lookup-chain-min` の parser、変換、補正。
- `engine/src/program/generate.cpp:5055-5062` — `--spec` / `--mtp-max-t` を基にした verify window 拡張。
- `engine/src/program/generate.cpp:1505-1541` — lookup に渡す context tail の構築と 64 token 上限。
- `engine/src/program/generate.cpp:22663-22679` — server 生成経路での適用条件、候補取得、policy gate。
- `engine/src/program/generate.cpp:23820-23823` — server stderr 集計。
- `engine/src/program/generate.cpp:24959-24974` — 非 server 生成経路での適用条件・policy gate。
- `engine/src/program/generate.cpp:25169-25172` — 非 server stdout 集計。
- `engine/src/spec/draft_source.cpp:13-31`、`engine/include/strata/spec/draft_source.hpp:19-64` — source 照会、最短一致条件、最長一致選択。
- `engine/src/spec/draft_policy.cpp:1009-1032` — 連鎖長を受理率・測定コストから選ぶ処理。
- `engine/src/spec/suffix_drafter.cpp:71-96` — prompt lookup が一致箇所の後続 token を提案する処理。

調査範囲はこの checkout の Strata 所有ソースと CLI 索引。安全に実行できる同一 revision の既存 engine `--help` は確認していない。SYCL parser にも同じ値変換がある（`engine/sycl/src/program/generate.cpp:2099-2100`）が、実行時の詳細説明は共通の `engine/src/program/generate.cpp` 経路を中心に記載した。backend ごとの性能差は調査・測定していない。
