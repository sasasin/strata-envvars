# `DS4_TL_DRAFT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。Strata リポジトリの作業ツリーは `main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数動作は対象外。

## 役割

Metal の DSV41 runtime で `DS4_TIMELINE` による dispatch timeline 計測が有効なとき、計測ゲートを speculative draft の GPU dispatch 中だけ開きます。これにより、timeline の timestamp 対象を draft 区間に絞れます。`DS4_TL_DRAFT` 自体は timeline 計測を有効にしません。

## 値と判定

| 状態 | 判定・結果 |
|---|---|
| 未設定 | `DS4_TL_DRAFT` によるゲート制御はしない。runtime の初期状態ではゲートは開いている。 |
| 設定あり | 値の内容を読まず、設定有無だけで有効。空文字、`0`、`false` を含め、どの文字列でも同じ。 |

数値変換、文字列比較、境界値判定、無効値時の fallback はありません。`src/dsv41/ds4_main.cpp` では最初の `tl_gate()` 呼び出し時に `static const bool` として設定有無を一度読み、そのプロセス内では再評価しません。Metal runtime 側では timeline の最初の encoder 初期化時に設定有無を読み、初期 gate を閉じます。実行中の環境変更は反映されません。

## 有効になる条件

- DSV41 engine が Metal 用 (`STRATA_METAL`) にビルドされ、Metal runtime の timeline 実装 (`STRATA_DS4_RUNTIME`) が含まれること。`ds4_main.cpp` のゲート呼び出しと `ds4_dispatch_seq()` 利用、および runtime の計測処理はそれぞれ該当 macro の条件付きです。
- `DS4_TIMELINE` が設定され、Metal runtime の timeline 計測が開始されていること。`DS4_TIMELINE` も値ではなく設定有無で判定されます。未設定なら `DS4_TL_DRAFT` を設定しても timeline は有効になりません。
- `DS4_TL_DRAFT` が設定されていること。未設定では timeline runtime の既定 gate が開いたままで、draft と verify 等の dispatch がともに記録候補になります。
- `round()` が speculative 経路に入ること: `spec` が真、`room > 1`、`m.draft_block() > 0`。これらを満たさない plain step には draft gate の開閉はありません。

設定時、各 speculative round は draft 前に gate を開き、draft 呼び出しの正常完了後に gate を閉じます。続く verify と plain step は閉じた状態です。したがって CLI/request の speculative decode が無効、または draft block がない場合、この変数による draft 限定計測区間は作られません。CLI から同名値を上書きする処理は見つかりませんでした。

## 実行時の詳細

`round()` の speculative 分岐で `tl_gate(false)` を初期化時に一度呼び、設定があれば `ds4_timeline_gate(0)` で gate を閉じます。各 draft の直前に `tl_gate(true)`、`m.draft()` が成功した後に `tl_gate(false)` を呼びます。Metal runtime の `tl_make_encoder()` は gate が閉じているとき、または `DS4_TL_AFTER` の dispatch 番号条件外・容量上限時には timestamp attachment のない encoder を返します。`DS4_TL_FROM` は記録後の集計で先頭 dispatch を読み飛ばす条件です。これは dispatch の計算・結果を変更するコードではなく、timeline の記録範囲を制御するものです。

環境変数だけを理由に出るログはありません。`DS4_TIMELINE` の計測が有効なら、終了時に `timeline: ...` の集計が stderr に出ます（記録 dispatch が 2 未満ならレポートは出ません）。timestamp counter set / sample buffer の取得失敗や counter range の resolve 失敗時は `mtl: DS4_TIMELINE: no timestamp counter set`、`mtl: DS4_TIMELINE: no counter sample buffer`、`mtl: DS4_TIMELINE: resolve failed` が stderr に出ます。これらは計測初期化・集計の失敗経路です。

`m.draft()` が失敗すると `round()` はその場で `false` を返し、直後の `tl_gate(false)` は通りません。通常の生成 caller は `ds4: <error>` 等を stderr に出して処理を中断します。この失敗経路では gate が閉じ直されない点に留意してください。

## 根拠

- 候補一覧への掲載: `docs/envvars/000_envvers.md:315`。
- 値の設定有無判定、Metal 条件付き呼び出し、speculative round 中の gate 開閉、draft 呼び出し失敗経路: `src/dsv41/ds4_main.cpp:198-214,218-235`。
- speculative 条件と plain-step fallback: `src/dsv41/ds4_main.cpp:223-229,241-273`。
- 生成 caller の speculative 条件、エラー時の stderr 出力と cancel: `src/dsv41/ds4_main.cpp:985-1001`。
- runtime の既定 gate、timestamp encoder 判定、および `DS4_TL_DRAFT` 読み取り: `metal/src/mtl_rt.mm:78-93,95-132`。
- runtime 側の timeline 有効化条件と終了時レポート登録: `metal/src/mtl_rt.mm:292-301`。終了時レポートの出力と失敗ログ: `metal/src/mtl_rt.mm:156-214`。
- Strata docs 内で `DS4_TL_DRAFT` の説明は確認できませんでした。上記は調査対象 commit の実装に基づきます。
