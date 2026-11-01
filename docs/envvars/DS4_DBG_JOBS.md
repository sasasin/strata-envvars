# `DS4_DBG_JOBS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `main` と `origin/main` の一致を示し、未コミット変更はありませんでした。

## 役割

DS4 の Metal host 実装が IQ matrix-vector dispatch を受け取ったとき、受け取った job の情報を標準エラーへ出す診断用スイッチです。出力するのは各 job の `type`、`n`、`k`、`ncol` です。この変数の読み取り自体は job の選択、分割、Metal kernel dispatch を変更しません。

## 値と判定

`std::getenv("DS4_DBG_JOBS")` の結果をポインタの真偽値として判定します。文字列の変換や比較はありません。

| 状態 | 動作 |
|---|---|
| 未設定 | この変数による job 診断出力なし |
| 空文字を含む、何らかの値を設定 | job 診断出力あり |

`0`、`false` なども設定済みなら出力を有効にします。既定では出力しません。CLI 引数、設定ファイル、別の環境変数との優先順位はありません。

## 有効になる条件

- `iq_mv()` が呼ばれ、`nj > 0` であること。`nj <= 0` なら関数は先に成功を返し、環境変数を調べません。
- Metal 側の `iq_mv()` が初期化 `ensure()` を通過すること。初期化に失敗すると環境変数を確認せず `false` を返します。
- 呼び出し元で `STRATA_METAL` が定義され、job 数 `n` が 1〜64 の場合に Metal host の `iq_mv()` が試されること。通常の呼び出し経路では Metal host が `true` を返すとその経路で処理されます。

従って、変数を設定しても非 Metal backend や Metal host の IQ dispatch を通らない実行では出力されません。OS、サーバーモード、CLI オプション、モデル状態による追加の条件はこの読み取り箇所にはありません。

## 実行時の詳細

`DS4_DBG_JOBS` は各 `iq_mv()` 呼び出しで都度読み取られ、値を static 変数へ保存しません。`iq_mv()` 呼び出しの開始時（`nj > 0` と `ensure()` 成功の後）に設定状態を確認します。プロセス中に環境を変更した場合、その後の呼び出しでは変更後の状態が参照されます。

設定されていると、stderr に `iq_mv call:` に続いて、入力配列の job ごとに ` [t<type> n<n> k<k> c<ncol>]` を連結し、最後に改行を出します。これは入力 job の一覧で、環境変数によるフィルタや変換を表すものではありません。出力後も関数は通常の処理を続けます。

`iq_mv()` が失敗を返した場合、呼び出し元 `mv()` は Metal host 経路の成功扱いにせず、同じ `mv()` の通常の job 処理へ進みます。job buffer の確保失敗時は stderr に `dsv41 metal: iq_mv job buffer failed` を出して `false` を返します。環境変数による警告、プロセス終了、timeout 経路はありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:727-739`: 早期 return と `ensure()`、環境変数の有無判定、stderr の出力内容。
- `metal/src/engine/ds4_finish.cpp:740-778`: 環境変数による分岐後の job 処理が続くこと、および先行する `DS4_NO_MVN` 判定など別設定の処理。
- `metal/src/engine/ds4_finish.cpp:780-810`: Metal buffer / pipeline の失敗時に `false` を返し、成功時に dispatch して `true` を返す経路。
- `src/dsv41/ds4_iq.cu:1694-1708`: `STRATA_METAL` ビルドで `1 <= n <= 64` のとき Metal host を試し、成功しない場合に通常経路へ進む呼び出し側。
- `metal/include/metal_compat/ds4_metal_host.h:44,91`: Metal host API の `iq_mv` 宣言。

候補一覧 `docs/envvars/000_envvers.md:151` に名前があります。`docs/DETAILS.md` は調査対象リポジトリに存在せず、この診断スイッチを説明する別の設計資料も確認できませんでした。
