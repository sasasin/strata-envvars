# `--spec`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。Strata checkout は `main...origin/main` で、`git status --short --branch` に変更表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はビルド対象カード数 2 / 3 / 4） |
| オプション | `--spec` |
| 別名 | なし |
| 値 | 整数。1〜15 |

## 役割

MTP draft layer が speculative decoding で作る draft chain の最大長 K を指定します。これは毎回必ず K 個の draft を作る指定ではありません。通常の単一要求では、既定で有効な適応処理が受理実績などから chain 長を 1〜K の範囲で選びます。また、文脈から n-gram lookup draft が得られる場合はそちらを先に使います（`src/split/src/session.cpp:411-425, 566-584`）。

## 使い方

```sh
strata-split-2 --serve --native /path/to/model.gguf --mtp /path/to/mtp-runtime --spec 4
```

`--serve`、`--native`、`--mtp` は起動に必要です。CMake target は `strata-split-2/3/4` で、`N` の build 制約は 2 / 3 / 4 です（`src/split/CMakeLists.txt:92-97`）。実配布時の実行ファイル名は GPU により異なります。索引の [strata-split 節](../../README.md#strata-split) を参照してください。

## 値と既定値

- 値は必須で、`std::stoi` で整数に変換されます。省略時は `6` です。同じオプションを複数回指定すると、`a.K` への代入が繰り返されるため最後の値が使われます（`src/split/tools/sfnx.cpp:65-68, 75-87`）。
- parser 自体は K の範囲を検査しません。Session の構築時に `1 <= K <= MAXT - 1` を検証します。`MAXT` は 16 なので、受理範囲は 1〜15 です（`src/split/src/session.cpp:140-144`、`src/split/src/model.hpp:43`）。
- `std::stoi` の呼び出しでは変換済み文字数を確認しないため、整数として読める先頭部分の後ろに文字が続く値は、その整数として扱われます。整数に変換できない値や `int` の範囲を超える値は変換例外になります（`src/split/tools/sfnx.cpp:85-87`）。
- `--spec` は MTP chain の上限であり、別 option `--lookup` の lookup draft 数を指定するものではありません（`src/split/tools/sfnx.cpp:65-68, 85-88`）。

## 実行時の動作

parser は値を `Args::K` に格納し、`Server` が各 Session に渡します（`src/split/tools/sfnx.cpp:65-68, 85-87, 435-445`）。単一要求の生成では、lookup draft が見つからない場合に MTP chain を作ります。`FNX_DRAFT_ADAPT` が未設定または 0 以外なら適応処理が既定で有効で、過去の chain draft の到達・採用状況を使って 1〜K の長さを選びます。`FNX_DRAFT_ADAPT=0` の場合は K 長を使います（`src/split/src/session.cpp:411-425, 566-584`）。環境変数の詳細は [`FNX_DRAFT_ADAPT`](../../../envvars/FNX_DRAFT_ADAPT.md) を参照してください。

`--batch` が 1 より大きく、`FNX_BATCH_DRAFTS` が `0` 以外（未設定時の既定は MTP）なら batch decoder が作られます。lookup draft が無い lane では、`--spec` の値、context の残り、およびその lane が現在保持する K/V page の範囲を使って MTP chain の候補上限を決め、複数 lane の window に収まるようさらに調整します。したがって、実際に使われる draft 数は K より少なくなる場合があります（`src/split/tools/sfnx.cpp:435-445`、`src/split/src/engine_common.cu:1020-1028`、`src/split/src/batch.cpp:64-68, 270-296`）。環境変数の詳細は [`FNX_BATCH_DRAFTS`](../../../envvars/FNX_BATCH_DRAFTS.md) を参照してください。

この option は起動時に読み取られ、Session と必要な batch decoder の設定に使われます。値を変更するための実行中更新経路は確認できません。`INFO engine=sfnx` の protocol 出力には指定後の `spec=<K>` が載ります（`src/split/tools/sfnx.cpp:1081-1083`）。

## 適用条件と副作用

- `strata-split` の `--serve` 起動で使われます。MTP chain の最大長を制限しますが、MTP runtime の選択や lookup draft の上限、生成時の受理規則は変更しません（`src/split/tools/sfnx.cpp:85-88`、`src/split/src/session.cpp:485-522, 566-584`）。
- 有効範囲の K でも、実際の chain は適応処理、lookup の有無、context の残り、batch window の容量などで短くなります（`src/split/src/session.cpp:458-462, 566-584`、`src/split/src/batch.cpp:270-296`）。
- 値自体がファイルやネットワークへ副作用を持つ処理は確認できません。engine / MTP のロードや GPU 初期化は `--spec` の範囲検査より先に進むため、無効範囲の値でも初期化コストが発生し得ます（`src/split/tools/sfnx.cpp:1040-1061`）。

## 出力とエラー

- 値を省略した場合は `--spec needs a value`、数値変換に失敗した場合は変換エラーが stderr に `sfnx: <理由>` として出て、終了コード 2 になります（`src/split/tools/sfnx.cpp:77-79, 85-87, 1040-1048`）。
- 1〜15 の範囲外では Session 構築が `session: K must be 1..15` で失敗します。この検査は model、MTP、engine の初期化後です。起動失敗経路では protocol stdout に `ERR <理由>`、stderr に `sfnx: failed: <理由>` が出て、終了コード 1 になります（`src/split/src/session.cpp:140-144`、`src/split/tools/sfnx.cpp:1030-1035, 1050-1061`）。
- 起動成功後は stdout の `INFO engine=sfnx version=0.2 spec=<K>` に設定値が含まれます（`src/split/tools/sfnx.cpp:1081-1083`）。

## 根拠

- option の parser、既定値、整数変換: `src/split/tools/sfnx.cpp:65-104`
- Session への値の転送と起動時のログ: `src/split/tools/sfnx.cpp:435-445, 1068-1083`
- K の範囲検査と `MAXT`: `src/split/src/session.cpp:140-144`、`src/split/src/model.hpp:43`
- 単一要求での adaptive chain 長と draft 作成: `src/split/src/session.cpp:411-425, 566-584`
- batch decoder における K の範囲検査と chain offer: `src/split/src/batch.cpp:64-68, 270-296`
- `FNX_BATCH_DRAFTS` の値と既定動作: `src/split/src/engine_common.cu:1020-1028`
- `strata-split-N` の target とカード数制約: `src/split/CMakeLists.txt:92-97`

## 調査範囲と制約

Strata の指定 checkout で parser から使用箇所までソースを確認しました。同一 revision の既存 `strata-split-N` バイナリの `--help` と Release artifact は確認していません。GPU 実機での値ごとの資源量・速度差も測定していません。
