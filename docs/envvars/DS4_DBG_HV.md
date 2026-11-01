# `DS4_DBG_HV`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリと GPU driver の動作は対象外。

## 役割

Metal 版 DeepSeek V4.1 エンジンで、埋め込み処理に渡された `rows` / `h` のポインターと、`strata::gpu::host_view()` が返すポインターの対応を stderr に出す診断用フックです。値を parse したり、計算・ポインター選択を変えたりしません。実際の host view の選択は別変数 `DS4_HOSTVIEW` が決めます。

この読み取りは `metal/src/engine/ds4_host.cpp` にだけあります。Metal 用 `strata_ds4` の `STRATA_METAL` ビルドで呼ばれる経路です。Metal 以外の DS4 ビルドと通常の `strata` エンジンには、この読み取り箇所がありません。

## 値と判定

`std::getenv("DS4_DBG_HV")` の null 判定だけを行い、値の内容は見ません（`metal/src/engine/ds4_host.cpp:112-114`）。

| 環境変数の状態 | 動作 |
|---|---|
| 未設定 | この診断行を出さない |
| 設定あり（空文字を含む） | 各対象呼び出しでポインター対応を stderr に出す |

`1`、`0`、任意の文字列を区別せず、変換、数値範囲、無効値時の fallback はありません。CLI 引数や設定ファイルとの優先順位もありません。この変数は診断出力だけを制御します。

## 有効になる条件

- macOS 向け Metal ビルドであること。`metal/CMakeLists.txt` は非 Apple で構成を失敗させ、`strata_ds4` ターゲットに `STRATA_METAL=1` を付けます（`metal/CMakeLists.txt:16-18,132-142,165-171`）。
- `src/dsv41/ds4_kernels.cu` の `embed()` が呼ばれること。これは Metal ビルドでは先に `metal_host::embed_addr()` を試し、その関数が成功するとそこで返るため、`DS4_DBG_HV` の読み取り箇所には到達しません（`src/dsv41/ds4_kernels.cu:2186-2193`, `metal/src/engine/ds4_host.cpp:195-224`）。
- `embed_addr()` が処理しない／失敗した後、`metal_host::embed()` がライブラリ初期化に成功し、host view が両方とも有効であること。ライブラリ不在時と host view 不在時は、それぞれ `dsv41 metal: embed: no library`、`dsv41 metal: embed has no host view` を stderr に出して `false` を返すため、この変数の診断行より先に終了します（`metal/src/engine/ds4_host.cpp:102-114`）。

この条件で `DS4_DBG_HV` が設定されていれば、ログは次の形式です（アドレス値は実行時のポインターです）。

```text
DBG hostview: rows %p -> %p   h %p -> %p
```

## 実行時の詳細

値は `metal_host::embed()` の呼び出しごとに `getenv()` で調べ、static cache しません（`metal/src/engine/ds4_host.cpp:102-114`）。したがって、プロセス環境を変更できる実行環境では、後続の呼び出し時に設定有無が再評価されます。モデル処理からの呼び出しは通常の draft、chunk、serial、複数デバイスの入力埋め込み箇所にあります（`src/dsv41/ds4_model.cu:7771,8628,8801,9782,9892`）。ただし、`embed_addr()` の先行経路が成功した呼び出しは `embed()` に進まず、この診断を出しません。

`DS4_DBG_HV` は `use_hv` を変更しません。`use_hv` は `DS4_HOSTVIEW` が未設定かどうかで別に決まり、その後、`rows` と `h` の実アドレスまたは `host_view()` の結果を使ってバッファーを wrap し、Metal kernel を dispatch します（`metal/src/engine/ds4_host.cpp:107-110,115-133`）。wrap 失敗なら `dsv41 metal: embed wrap failed` を出して `false` を返し、呼び出し元の `src/dsv41/ds4_kernels.cu:2191-2193` では通常の `embed_kernel` に進みます。

## 根拠

- 環境変数の唯一の直接参照、設定有無判定、ログ文字列: `metal/src/engine/ds4_host.cpp:102-114`。
- 読み取りを囲む Metal 埋め込み処理と失敗経路: `metal/src/engine/ds4_host.cpp:102-133`。
- 呼び出し順と fallback: `src/dsv41/ds4_kernels.cu:2186-2193`。
- `embed_addr()` の先行 dispatch と成功時の戻り: `metal/src/engine/ds4_host.cpp:195-224`。
- Metal / `strata_ds4` のビルド条件: `metal/CMakeLists.txt:16-18,132-142,165-171`。
- 候補一覧には名前があります（候補一覧: `strata-envvars/docs/envvars/000_envvers.md:149`）。Strata の `docs/DETAILS.md` にこの診断変数の追加説明は見当たりませんでした。
