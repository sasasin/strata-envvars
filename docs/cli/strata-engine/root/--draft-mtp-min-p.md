# `strata --draft-mtp-min-p`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ推論エンジン `strata`（root） |
| オプション | `--draft-mtp-min-p` |
| 別名 | なし |
| 値 | `P`。数値を `atof` で読み、`0.0..1.0` に clamp |

## 役割

`--draft auto` を使う server のうち、MTP drafter を選んだリクエストに対して、MTP の speculative draft を受理候補へ含める確率下限を指定します。指定値未満の確率の draft で窓を打ち切るための `--spec-min-p` 相当値です。DFlash2 を選ぶリクエストにはこの設定は適用されません（`src/program/generate.cpp:995-1000,1162-1165,15211-15230`）。

## 使い方

```sh
strata --native MODEL.gguf --mtp MTP_DIR --draft auto --draft-model DFLASH2_PACK \
  --draft-mtp-min-p 0.20 --serve
```

これは `--draft auto` の server を起動し、MTP を選ぶリクエストの閾値を `0.20` にする例です。モデル、MTP データ、DFlash2 pack は実際の環境に合わせて指定してください。`--draft auto` は両方の drafter を保持し、個々のリクエストが `draft=mtp|dflash2` で選びます（`src/program/generate.cpp:1163-1164,15120-15122`）。

## 値と既定値

- 値は `std::atof` で読み取られ、`std::clamp(..., 0.0, 1.0)` により範囲内へ丸められます。範囲外の数値はエラーではなく端点になります。数値として解釈できない文字列は `atof` の規則で `0` になります（`src/program/generate.cpp:3580-3582`）。
- オプション省略時の内部値は `-1.0` です。この sentinel によって、`--draft auto` の MTP リクエストはグローバル `--spec-min-p` の値を引き継ぎます（`src/program/generate.cpp:892,1000,15120-15122,15230`）。
- 明示値の `0` は確率下限を無効にします。負数を明示すると parser が `0` に clamp するため、既定値の「`--spec-min-p` を引き継ぐ」状態にはなりません（`src/program/generate.cpp:3581,1000,15230`）。
- 同じオプションを複数回指定した場合は parser が順に代入し、最後の値が残ります（`src/program/generate.cpp:3490-3582`）。値を省略すると `--draft-mtp-min-p needs a value` を stderr に出して終了コード `2` で終了します（`src/program/generate.cpp:3295-3297`）。

## 実行時の動作

リクエストごとの基準値 `req_spec_min_p` は、まずグローバル `--spec-min-p` から初期化されます。server request の `spec_min_p=...` があると、その値を `0..1` に clamp して使い、`req_min_p_set` を立てます（`src/program/generate.cpp:15118-15122,15168-15171`）。

`--draft auto` が有効で DFlash2 drafter も使用可能な場合、リクエストの `draft=` 指定（なければ `--draft-rule`）に従って drafter を選びます。選択結果が MTP で、かつそのリクエストに `spec_min_p=` が明示されていないときだけ、オプションの値が `req_spec_min_p` に上書きされます（`src/program/generate.cpp:15211-15230`）。この閾値は MTP の draft/window 判定に渡されます（`src/program/generate.cpp:17596-17602,18585-18588`）。

したがって、リクエスト側の `spec_min_p=` はこの CLI 設定より優先します。オプション単独では `--draft auto` を有効化せず、また非 auto の MTP 実行では参照されません。`--draft auto` 自体は `--serve` 用の二 drafter 選択モードです（`src/program/generate.cpp:995-1000,1163-1164`）。

## 適用条件と副作用

- `--draft auto` による MTP リクエストでのみ適用されます。DFlash2 リクエストでは値を切り替えません（`src/program/generate.cpp:15211-15230`）。
- server request ごとに閾値を決めるため、他リクエストへ値を持ち越す設定ではありません。明示された request `spec_min_p=` はその request の閾値として使われます（`src/program/generate.cpp:15118-15122,15168-15171,15230`）。
- parser の範囲内に専用の validation error はありません。オプション自体はファイルやネットワークへ書き込みません。実行時には draft 窓の長さ・候補範囲を確率で制限します（`src/program/generate.cpp:17596-17602,18585-18588`）。

## 出力とエラー

値の範囲外や数値でない文字列を専用エラーとして拒否する処理は確認できません。値が欠ける場合は parser が stderr に不足を表示して終了コード `2` で終了します（`src/program/generate.cpp:3295-3297,3581`）。このオプション専用の起動時メッセージは確認できません。

## 根拠

- 宣言時の既定値と sentinel の説明: `src/program/generate.cpp:995-1000`
- help の用途説明: `src/program/generate.cpp:1162-1165`
- parser、型変換、clamp: `src/program/generate.cpp:3295-3297,3580-3582`
- request ごとの初期値と `spec_min_p=` の優先: `src/program/generate.cpp:15118-15122,15168-15171`
- drafter 選択と閾値の適用条件: `src/program/generate.cpp:15211-15234`
- 閾値を使った窓長と draft 処理: `src/program/generate.cpp:17596-17602,18585-18588`

調査範囲はこの revision の `src/program/generate.cpp` にある parser と server request 処理です。別 backend のビルド実行や実バイナリでの動作確認は行っていません。
