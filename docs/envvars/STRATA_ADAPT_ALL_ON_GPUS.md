# `STRATA_ADAPT_ALL_ON_GPUS`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL エンジンで、主 GPU の常駐表にない専門家が helper GPU または peer cache に保持されている場合も「全専門家が GPU 上にある」と判定するための opt-in フラグです。その条件を満たすと適応層を止め、主 GPU と CPU/host の間で専門家を入れ替える処理を避けます。変数自体が専門家の配置を行うわけではありません。判定と適応層の初期化は `engine/sycl/src/program/generate.cpp:8687-8711` にあります。

この読み取りは SYCL エンジンの `generate.cpp` にだけあり、CUDA 実装には同名の読み取りがありません。SYCL エンジンの CMake 定義は `engine/sycl/CMakeLists.txt:375` でこの `generate.cpp` を解決し、同 CMake は Linux x86_64 の SYCL エンジンとして構成されています（`engine/sycl/CMakeLists.txt:255`）。

## 値と判定

`std::getenv` の戻り値が null でなく、先頭文字が文字 `'1'` の場合だけ有効です。文字列全体の比較や数値変換は行いません。未設定・空文字は無効です。`1`, `10`, `1anything`, `1 ` は有効、`0`, `true`, ` 1`, `01`, `2` は無効です。大文字小文字・空白の正規化や後続文字列の検証もありません。結果は関数内 `static const` に保存されます（`engine/sycl/src/program/generate.cpp:8692-8695`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| SYCL エンジン | OFF | `1`, `1anything` | 空文字、`0`, `true`, ` 1` |

## 有効になる条件

- `host_res` が空でないこと。
- 主 GPU にない専門家が存在し、`drive.d.remote_count > 0` または `peer.valid()` であること。
- 主 GPU にないすべての専門家について、少なくとも一つの remote helper (`remote[r]->holds`) または peer cache (`peer.has`) が保持していること。1 件でも保持先がなければ「全専門家が GPU 上」とは判定されません（`engine/sycl/src/program/generate.cpp:8695-8706`）。
- この判定で適応層を止めるには、さらに `--adapt-every > 0` かつ `--adapt-swaps > 0` が必要です。両 CLI 値は SYCL エンジンで既定 `4` と `96`、CLI から整数として設定されます。どちらかが 0 以下なら適応用 usage 配列の割り当て・停止ログ条件を満たしません（既定値: `engine/sycl/src/program/generate.cpp:692-695,721`; parse: `2052,2166`; 判定: `8710-8711`）。
- すでに全専門家が主 GPU に常駐している場合は、この環境変数が無効でも `all_experts_resident` により適応層の usage 配列を作りません。このケースでは helper/peer 向けの停止ログも出ません（`engine/sycl/src/program/generate.cpp:8687-8688,8707-8711`）。

## 実行時の詳細

読み取りは対象コード経路が初めて評価されたときに一度行い、関数内 `static const` に保持します。その後のリクエストやプロセス環境の変更では再評価されません（`engine/sycl/src/program/generate.cpp:8694`）。

値が有効で、主 GPU にない全専門家を helper/peer が保持し、適応 CLI 条件も満たす場合、`all_experts_on_gpus` が true となり、`drive.d.usage` を割り当てないため適応処理が動きません。条件を満たさない場合は、適応 CLI 条件が有効なら usage を割り当て、通常の適応処理が継続します。通常経路はルーティング使用数を集計し、各層で主 GPU にない候補と常駐中の専門家を比較して最大 `--adapt-swaps` 件まで交換します。また peer cache が有効なら適応時に peer 側の cache も更新します（`engine/sycl/src/program/generate.cpp:8710-8711,8825-8852,9000-9008`）。

この変数は値の受け渡しや子プロセス起動には使われず、CLI 値を上書きもしません。`--adapt-every` と `--adapt-swaps` は適応処理を許可する別条件です。適応処理は usage 配列が空でないこと、間隔 `--adapt-every` に達したことなどを条件に起動します（`engine/sycl/src/program/generate.cpp:12031-12043`）。

## ログと測定値

適応 CLI 条件が有効で、全専門家が主 GPU ではなく helper/peer を含む GPU 上にあると判断された場合、stderr に次の文字列を出します。

```text
strata generate: every expert is on a GPU (primary + helper/peer caches); adaptive tier off
```

主 GPU に全専門家が常駐する場合や、helper/peer 側に未保持の専門家がある場合、このログ条件には入りません（`engine/sycl/src/program/generate.cpp:8707-8709`）。`docs/DETAILS.md` にこの変数の説明や測定値は見つかりませんでした。ソースコメントには二枚の GPU の一試行で `32.1` から `61.3 tok/s` とありますが、「we have not measured」と明記された未測定値なので、性能値としては扱いません（`engine/sycl/src/program/generate.cpp:8692-8693`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:8687-8711` — 主 GPU の常駐判定、環境変数の読み取り、helper/peer の完全被覆判定、ログと usage 配列の条件。
- `engine/sycl/src/program/generate.cpp:8825-8852,9000-9008` — 適応処理の対象選択と peer cache への適用。
- `engine/sycl/src/program/generate.cpp:12031-12043` — 使用数と `--adapt-every` に基づく適応処理の起動。
- `engine/sycl/CMakeLists.txt:255,375` — SYCL エンジンの対象プラットフォームと `generate.cpp` のビルド定義。
