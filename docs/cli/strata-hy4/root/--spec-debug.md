# `--spec-debug`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--spec-debug` |
| 別名 | なし |
| 値 | なし（フラグ） |

## 役割

DFly2 speculative decoding の反復ごとの診断情報を標準エラーへ出します。生成内容や speculative decoding の設定を変更するオプションではありません。

## 使い方

```sh
strata-hy4 --model MODEL.strata --tokens prompt.ids --draft dfly2 --gen 32 --spec-debug
```

モデルと入力 token ファイルを指定して DFly2 による生成を行う例です。`--spec-debug` は値を取らないフラグです。

## 値と既定値

値は不要です。parser はこの引数を読むと `scfg.debug = true` に設定します。設定構造体の初期値は `false` です。明示的な値の範囲検証はありません。重ねて指定しても同じ真偽値を設定するだけです。値を付ける構文ではないため、たとえば `--spec-debug 1` の `1` はこのオプションの値として消費されず、通常の引数として解釈されます（認識されなければ unknown arg で終了します）。

## 実行時の動作

設定は `SpecCfg` として speculative decoder に渡されます。各 speculative 検証反復の処理後、`debug` が真なら `[spec]` 行を `stderr` に出します。行には prompt 位置 `a`、検証窓 `T`、分岐の有無 `branched`、受理数 `n`、draft と verify の所要時間（ms）、最大3ノードの confidence が含まれます。生成 token や検証結果を変える分岐はこのフラグによって追加されません。

通常のオフライン生成では `--draft dfly2` と `--gen` が正の値である場合に speculative decoding の経路へ進みます。`--serve` でも同じ設定が server に渡され、drafter が有効になったときの `Spec` に適用されます。したがって `--spec-debug` 単独では反復ログは出ません。

## 適用条件と副作用

ログは speculative decoder の反復が実際に走った場合に限って出ます。server 経路では `--draft` が `off` 以外で、chunk が8以上かつ DFly2 初期化に成功した場合に speculative decoder が有効になります。chunk が小さい場合や drafter の初期化に失敗した場合は server は drafter なしで続行するため、このログも出ません。

副作用は反復ごとの標準エラー出力と、その出力に伴う I/O です。ファイルやネットワークへの書き込みはこのオプションの処理にはありません。値の validation、fallback、環境変数との優先順位はありません。

## 出力とエラー

ログの形式は次の通りです（数値・値は実行時のものです）。

```text
[spec] a=... T=... branched=... n=... draft ... ms verify ... ms conf ... ... ...
```

`--spec-debug` 固有のエラー経路は確認できません。値を取らないため値の validation error もありません。未知の余分な引数は parser が `unknown arg <引数>` を標準エラーへ出し、終了コード `2` を返します。

## 根拠

- parser とフラグ設定、値を要求する引数の不足時の処理: `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,408-412`
- 未知引数の処理: `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505`
- `SpecCfg.debug` の既定値: `engine/src/hy4flash/run/hy4_spec.hip.h:18-30`
- `[spec]` ログと出力先（`stderr`）: `engine/src/hy4flash/run/hy4_spec.hip.h:491-498`
- オフライン生成で speculative decoder を使う条件と構築: `engine/src/hy4flash/run/hy4_main.hip.cpp:700-701,992-1008`
- server への設定引き渡し: `engine/src/hy4flash/run/hy4_main.hip.cpp:544-557`
- server 側の drafter 条件と `Spec` 構築: `engine/src/hy4flash/run/hy4_serve.hip.h:319-341`
- 文書の tool ID・scope・掲載位置: `docs/cli/README.md:1277-1281,1333-1336`
