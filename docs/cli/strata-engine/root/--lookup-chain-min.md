# `--lookup-chain-min`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の engine 引数（`generate` 実行経路） |
| オプション | `--lookup-chain-min` |
| 別名 | なし |
| 値 | 整数 `M`。照合対象にする末尾コンテキストの最小 token 数。実効値は最低 3。 |

## 役割

`--lookup-chain` が MTP の draft の後ろに prompt lookup draft を継ぎ足すとき、候補を採用するために必要な context match の最小長を指定します。`--lookup-chain-min` 単独では lookup chain は有効になりません。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --lookup-chain 2 --lookup-chain-min 8
```

これは構文例です。`--pack` と token 列は実際に利用するモデル・入力に合わせてください。

## 値と既定値

- 既定値は `3` token です。
- parser は次の引数を `atoi` で整数化し、`std::max(3, 値)` を設定します。したがって `3` 未満の整数（負数を含む）は `3` に補正され、3 未満を指定して lookup を無効にはできません。
- `atoi` が数値として読めない値も `0` となり、この parser ではエラーにせず実効値 `3` になります。上限の clamp はありません。
- 同じオプションを複数回指定した場合、走査中に値が順次代入されるため最後の指定が残ります。
- 値を省略すると `next` が `--lookup-chain-min needs a value` を stderr に出して終了コード `2` で終了します。

## 実行時の動作

値は、候補 source の提案長ではなく、その候補が根拠とする末尾 context の match 長に対する閾値です。engine は prompt lookup source と登録済みの追加 draft source を調べ、match 長がこの値以上で、これまでの候補より長い source の提案を採用します。同じ match 長なら先に調べた source が残ります。内蔵 source は request の prompt と確定済み出力を履歴に持ち、MTP draft を仮の末尾として lookup を続けます。

通常の生成ループでは、`--lookup-chain > 0`、初回ではない window、suffix lookup による window 置換がないこと、そして window に余地があることが実行条件です。サーバーの batch/serve ループにも同様の条件があり、MTP が有効で、初回でなく、suffix lookup を使わず、window の空きがある場合だけ提案を求めます。提案数は `--lookup-chain` の値と空き行数の小さい方までです。採用された token は MTP の draft に続けて同じ verify window に入り、greedy 検証を通った token だけが出力に残るため、この候補 source 自体は生成内容を直接確定しません。

通常は `DraftPolicy::chain` が候補数をさらに絞ります。MTP の draft 確率、過去の chained draft 受理数、match 長別の受理率、および window 幅ごとの測定コストを使って、期待 token 数/時間が改善すると見込む幅を選びます。`STRATA_LOOKUP_CHAIN_FIXED` が環境に存在するとこの policy gate を迂回し、得られた提案をそのまま使用します（値の内容ではなく変数の存在を判定）。この環境変数は `--lookup-chain-min` の閾値を変更しません。

## 適用条件と副作用

- `--lookup-chain` の既定値は `0`（off）です。正の値を指定しない限り、閾値は実行時の候補検索に使われません。`--lookup-chain` は parser で `0..7` に clamp されます。
- 有効時も、初回 window、既に suffix lookup の window を選んだ場合、window の残りがない場合は chain 候補を検索しません。通常生成経路では `T < S`、サーバー経路では MTP 有効かつ `T < room` が条件です。
- prompt lookup は通常、request の prompt と受理済み token の履歴を参照します。履歴照合および追加 source の参照が行われますが、この option 固有のファイル・ネットワーク書き込みは確認できません。
- 検証窓の大きさは最大 8 行です。chain 用の窓サイズ調整は `--lookup-chain` の設定値を使い、`--lookup-chain-min` の数値では窓幅を変えません。

## 出力とエラー

不足値は上記のとおり stderr と終了コード `2` になります。範囲外や非数値の値に対する個別の警告・拒否はなく、下限 3 へ補正されます。未知の引数は通常の parser 経路で `unknown argument` と usage を stderr に出して終了コード `2` になります。

サーバー経路では `--lookup-chain` 有効時に `DONE` レコードへ chain accepted/offered、suffix accepted/offered、window 数が追加されます（`src/program/generate.cpp:15365-15388`）。この記録は `--lookup-chain-min` 単独の指定有無を示すものではありません。通常生成経路も chain window/draft/accepted の集計を行います（`src/program/generate.cpp:16455-16467`, `16679-16715`, `16744`）。

## 根拠

- 索引上の scope と文書配置: `docs/cli/README.md:1128-1134`, `1195-1200`（`strata-engine` の root engine 引数）。索引の説明では parser の根拠を `src/program/generate.cpp` としています。
- parser 既定値: `src/program/generate.cpp:780-784`。
- help 表示と説明: `src/program/generate.cpp:942-944`。
- 値の取得、整数変換、下限補正: `src/program/generate.cpp:2418-2420`, `2674-2675`。
- 不足値と未知引数の失敗経路: `src/program/generate.cpp:2418-2420`, `2787-2793`。
- chain window の上限調整: `src/program/generate.cpp:3212-3219`。
- 通常生成経路の条件、閾値の適用、候補の window 追加: `src/program/generate.cpp:14904-14929`。
- サーバー経路の条件と閾値適用: `src/program/generate.cpp:16567-16584`。
- source 選定で match 閾値・最長 match を使う処理: `src/spec/draft_source.cpp:13-34`; interface の説明: `include/strata/spec/draft_source.hpp:29-33`, `57-60`。
- 内蔵 prompt lookup source が MTP draft を末尾として提案する処理: `include/strata/spec/draft_source.hpp:36-52`。
- suffix matcher の match 判定・最大 64 token の match と続きの提案: `src/spec/suffix_drafter.cpp:64-95`。
- policy gate と `STRATA_LOOKUP_CHAIN_FIXED` の条件: `src/program/generate.cpp:14912-14917`, `16577-16581`; policy の選択: `src/spec/draft_policy.cpp:226-253`。
- server の `DONE` レコード: `src/program/generate.cpp:15365-15388`。

調査範囲は上記 commit の checkout 内ソースです。Release 配布物との照合や実機での CLI 実行は行っていません。
