# `STRATA_HEAD_ALIAS_TEST_MOVE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`--prefill-head-alias` でプロンプト読込中にアンロードしていた native output head を復元するとき、head の重みサイズと同じ CUDA メモリ領域を一時確保したまま head をロードする診断用フックです。これにより再ロード後の head が以前と異なるアドレスへ配置される状況を作り、アドレスが変わった場合の verify window graph の破棄・再キャプチャ経路を通します。生成内容や head の計算方法を直接切り替える設定ではありません。読み取りと処理は `engine/src/program/generate.cpp` の serve リクエスト内 `head_restore` lambda にあります（19058-19096行）。

## 値と判定

`std::getenv(...) != nullptr` の設定有無だけで判定します。文字列の parse や値比較はありません。したがって未設定なら無効、設定されていれば空文字を含むどの値でも有効です。`1` だけでなく `0`、`true`、`false`、空文字、`0anything`、空白だけの値も有効です。大文字小文字、数値としての妥当性、前後の空白は検査されません（`engine/src/program/generate.cpp:19062-19069`）。

| 条件（build / 実行経路） | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `generate.cpp` の CUDA 実行経路で `head_restore` が呼ばれる | spacer を要求しない | 設定された任意の値（`1`、`0`、空文字など） | 該当なし。空文字も設定あり |
| 環境変数が設定済みでも `head_restore` が呼ばれない、または head がすでに loaded | 効果なし | 値にかかわらずこの呼出しでは読込・割当なし | 該当なし |

候補一覧の設定レジストリには `=1` と記載されていますが、コードは値を比較せず `getenv` の null 判定だけを行います。従って `=1` は有効な例であって必須値ではありません（`terminal/data/settings-register.json:14107-14120,14135`、`engine/src/program/generate.cpp:19065`）。

## 有効になる条件

- `--prefill-head-alias` が指定されている必要があります。このオプション自体がなければ lambda は `native_head.loaded()` と合わせて早期 return し、この環境変数は実行時に参照されません（`engine/src/program/generate.cpp:19058-19065`）。
- `--prefill-head-alias` は `--serve`、単一 GPU、`--batch` なし、`--pipeline-windows` なし、`--short-read 0`、`--expert-cache 1` または `auto`、`--mtp`、native output head が loaded という条件を満たす必要があります。満たさない場合は stderr に `strata generate: --prefill-head-alias is unavailable: ...` を出して終了コード 2 になります（`engine/src/program/generate.cpp:8372-8385`）。
- 対象箇所は CUDA API（`cudaMalloc`, `cudaGetLastError`, `cudaFree`）を使う CUDA 系の generate 実装です。候補一覧も backend を `cuda-hip` としています。SYCL 実装でこの名前の読み取りは見つからず、SYCL の prefill 実装は hybrid borrowed/owned layout を未対応としてエラーにします（`engine/src/program/generate.cpp:19065-19071`、`engine/sycl/src/prefill/prefill.cpp:1395`）。
- 初回起動時に head が loaded のままなら `head_restore` は何もしません。設定値が有効でも、そのリクエストで head が再ロードされない限り spacer は確保されません（`engine/src/program/generate.cpp:19058-19060`）。

## 実行時の詳細

環境変数は `head_restore` lambda 内の関数ローカル `static const bool` で読み取られます。lambda の最初の実行時に一度だけ `getenv` の結果を保存し、そのプロセス中の後続リクエストでは環境変更を再評価しません。読み取りは起動時ではなく、`--prefill-head-alias` を使う serve リクエストで head を復元する段階です。呼出し前に head が loaded なら早期 return するため、static 初期化も遅延します（`engine/src/program/generate.cpp:19058-19065,21519-21525`）。

環境変数が設定されている場合、`cudaMalloc` で `native_head.weight_bytes()` 分の spacer を確保し、成功すればその領域を保持した状態で `native_head.load(...)` を実行します。割当失敗は `cudaGetLastError()` でエラー状態を消費し、spacer を使わず head のロードを続けます。head をロードした後、確保できていた spacer は `cudaFree` されます（`engine/src/program/generate.cpp:19065-19074`）。

ロードに失敗すると stdout に `ERR restoring the native output head failed: ...` を出し、戻り値 1 で処理を止めます。ロード後の weights または scratch のアドレスが保存済みアドレスと異なる場合、`ver.drop_window_graphs` を呼んで captured verify window graphs を破棄します。破棄失敗時は stdout に `ERR --prefill-head-alias: the output head came back at another address and the captured verify graphs could not be dropped: ...` を出して戻り値 1 になります。成功時は stderr に破棄数と、以降各サイズの window で再キャプチャする旨を出します。設定自体を示す専用ログはありません（`engine/src/program/generate.cpp:19076-19096`）。

## ログと測定値

この環境変数による spacer の割当成否を直接示すログはありません。関連経路では、head のアドレス変化と graph 破棄成功時に stderr へ `strata serve: --prefill-head-alias: the output head came back at another address: %d window graphs dropped, each is captured again at its next window`、head 再ロード成功時に `strata serve: --prefill-head-alias: output head restored in %.1f ms before decode` を出します。graph 破棄失敗と head 再ロード失敗の出力は実行時の詳細に記載したとおりです（`engine/src/program/generate.cpp:19072-19096`）。

`docs/DETAILS.md` と `docs/PREFILL_HEAD_ALIAS.md` は `--prefill-head-alias` の機能・測定を扱っていますが、このテスト用環境変数による spacer 挙動の測定値は記載していません。対象変数の性能・正確性測定値は確認できません（`docs/DETAILS.md:1246`、`docs/PREFILL_HEAD_ALIAS.md:1-8`）。

## 根拠

- `engine/src/program/generate.cpp:8372-8393` — `--prefill-head-alias` の実行条件、初期 head の unload。
- `engine/src/program/generate.cpp:19058-19096` — 遅延 static 読み取り、spacer の割当・解放、head 復元と graph の再配置処理・ログ。
- `engine/src/program/generate.cpp:21519-21525` — prompt 完了後の `head_restore` 呼出し。
- `engine/sycl/src/prefill/prefill.cpp:1395` — SYCL 側の hybrid layout 非対応。
- `terminal/data/settings-register.json:14107-14135` — 候補登録と `=1` という注記。実際の値判定はコードを根拠とする。
- `docs/DETAILS.md:1246`、`docs/PREFILL_HEAD_ALIAS.md:1-8` — 関連する CLI 機能の説明。対象環境変数の測定値の根拠ではない。
