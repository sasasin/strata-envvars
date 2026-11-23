# `--draft-mtp-spec`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（engine の root parser。生成・serve の両モード） |
| オプション | `--draft-mtp-spec` |
| 別名 | なし |
| 値 | 整数 `N`。MTP drafter が使う検証窓の上限（トークン数） |

## 役割

`--draft auto` で DFlash2 と MTP をリクエストごとに選ぶ serve モードにおいて、MTP を選んだリクエストの speculative verify window を制限します。また、`--draft dflash2` が MTP に fallback する場合には、明示した値を MTP 窓幅の上限として適用します。DFlash2 の窓幅そのものを設定するオプションではありません。

## 使い方

```sh
# serve の auto drafting で、MTP リクエストの窓を最大 4 トークンにする。
strata --serve --pack ./target.gguf --mtp ./mtp --draft auto \
  --draft-model ./dflash2.pack --spec 8 --draft-mtp-spec 4
```

## 値と既定値

- 省略時の内部既定値は `4` です。`--draft auto` の MTP リクエストでは、この既定値が使われます。
- parser は `N` を `atoi` で整数変換し、`max(2, N)` に補正します。したがって `2` 未満や整数として読めない文字列は `2` になります。上限値自体の検証や上限側の clamp はありません。実際の窓幅は `--spec`、`--mtp-max-t`、ビルドの窓幅上限などでも制限されます。
- 同じオプションを複数回指定すると、parser の逐次代入により最後の値が残ります。
- 値を省略すると parser の `next` が stderr に `--draft-mtp-spec needs a value` を出して終了コード `2` で終了します。

## 実行時の動作

`--draft auto` は parser 内部では DFlash2 を基準 drafter にしつつ auto フラグを立てます。serve の各リクエストは要求の `draft=mtp|dflash2`、または `--draft-rule`（既定 `df2`）で drafter を決めます。MTP が選ばれた場合の窓幅は `min(S_mtp_wide, max(2, N))` です。ここで `S_mtp_wide` は、`--spec` と `--mtp-max-t` を反映した MTP 窓幅です。DFlash2 が選ばれたリクエストではこのオプションによる縮小は行わず、prompt-lookup の上限も MTP リクエストでは MTP 窓幅に合わせます。MTP の最大 draft 数も選ばれた幅に合わせて更新されます。

`--draft dflash2` で DFlash2 が起動できず MTP に切り替わる場合、このオプションを**明示していれば** `--spec` が `N` より大きいときに `--spec` を `N` まで下げます。明示の有無を別フラグで追跡するため、省略時の内部既定値 `4` はこの fallback 経路では上限として適用されません。DFlash2 が正常に起動する場合、または `--draft mtp` を直接指定する場合は、この fallback 用の補正はありません。

## 適用条件と副作用

- auto による drafter の切替は `--serve` のリクエスト処理で行われます。`--draft auto` は両方の drafter を保持し、ソースの起動条件では1 GPU・1リクエストの構成に限られます。DFlash2 が利用できない build / 実行条件では auto の切替自体が成立しません。
- MTP の窓幅が変わると、MTP が提案する token 数、verify 処理、および MTP リクエストの lookup 上限が変わります。これは推論処理の GPU / CPU 作業量に影響しますが、このオプション自体によるファイル生成、ネットワークアクセス、モデルの書き換えは確認できません。
- `--spec` や `--mtp-max-t` が小さい場合、指定値より実効窓幅が小さくなります。窓幅を 2 未満にはしません。

## 出力とエラー

この値に対する独立した validation error はありません。整数変換後に下限 2 へ補正します。欠落値は前述のとおり stderr と終了コード `2` で拒否されます。DFlash2 fallback の失敗・警告出力は DFlash2 起動経路によるもので、このオプション固有の出力ではありません。

## 根拠

- `engine/src/program/generate.cpp:1190-1195` — `--draft auto`、値の既定値 `4`、fallback で明示指定を区別するフラグの定義。
- `engine/src/program/generate.cpp:1359-1367` — parser の help に記載された `auto` と MTP 窓の説明、既定値 `4`。
- `engine/src/program/generate.cpp:3837-3842` — 値を取る引数の欠落時に stderr へ出力して終了コード `2` とする共通処理。
- `engine/src/program/generate.cpp:4138-4148` — `--draft auto` の内部表現と `--draft-mtp-spec` の `atoi`・下限 clamp・明示フラグ。
- `engine/src/program/generate.cpp:8195-8201` — DFlash2 利用条件と、auto が split / batch と併用できない起動条件。
- `engine/src/program/generate.cpp:8254-8255`、`13519-13528`、`24407-24430` — DFlash2 が使えず MTP に fallback するときの出力、終了経路、および明示値による `--spec` の縮小。
- `engine/src/program/generate.cpp:16295-16303` — `--spec` / `--mtp-max-t` から MTP 窓幅を作り、auto 時に本オプションで MTP 側だけを制限する処理。
- `engine/src/program/generate.cpp:18876-18900` — request ごとの drafter 選択、MTP の窓幅と lookup 上限、MTP 最大 draft 数の更新。
- 索引 `docs/cli/README.md:1036-1077` — `strata-engine` root parser の scope と本オプションの配置先。
- 調査基準 `docs/cli/001_investigation.md:17-54, 57-80, 112-162` — 配置、索引、parser から効果まで追う基準。

調査範囲は上記 checkout の Strata ソースです。CLI `--help` の実行は補助資料として使用していません。
