# `STRATA_VERIFY_STEPPED`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL backend の speculative verify window を、GPU とホストのフラグ通信をカーネル実行中に行わず、複数の SYCL graph segment に分けて実行する opt-in 設定です。各 segment がキュー上で完了した境界でホストが CPU 側の expert pool を処理して必要なフラグを立て、次の segment を進めます。全 expert が VRAM 常駐の経路では、ウィンドウ実行前に必要なホスト側 flag を立てます。これは実行・同期方式を選ぶ設定で、モデルの計算内容そのものを切り替える分岐としては使われていません。

この実装は `sycl/src/core/verify.cpp` にあり、CUDA/HIP 側の実装に同名変数の読み取りはありません。SYCL の verify 実行経路に限られます。

## 値と判定

`env_on()` は `getenv()` が null でないことに加え、空文字ではなく、先頭文字が `0` でないことを条件にします。文字列全体の parse や数値変換はしません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `0` または `0` で始まる文字列（例: `0abc`） | 無効 |
| その他（例: `1`, `true`, `false`, `2`, `abc`） | 有効 |

大文字小文字、空白、後続文字の検査はありません。`g_stepped` は翻訳単位のグローバル `const bool` として初期化されるため、プロセス起動時に一度だけ読み取られ、起動後の環境変更は反映されません。

根拠: `sycl/src/core/verify.cpp:92-103`。

## 有効になる条件

- SYCL backend の verify 実装を使用している必要があります。
- 通常の doorbell 経路では `STRATA_VERIFY_EAGER` が未設定のときに segment graph を capture し、capture 済み segment がある場合に stepped 実行します。`STRATA_VERIFY_EAGER` が設定されていると（値が空でも）この segmented capture/run 経路は選ばれません。
- すべての expert が VRAM 常駐のときは別経路で、`STRATA_VERIFY_EAGER` の有無によらず stepped 用の flag を launch 前に立てます。ただしテスト用 `g_test_stall` が対象 window に一致すると、この分岐を抑制します。
- segmented な通常経路で `--remote-expert-opt` が有効だと実行時に `verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` で失敗します。このエラー判定は segmented 経路に置かれ、all-resident の分岐にはありません。
- `STRATA_VERIFY_SPLIT` は segment の切り方に関係します。既定では split point hook を設定し、`STRATA_VERIFY_SPLIT=0...` で無効にします。`STRATA_VERIFY_PIPE` は split segment に続く CPU 処理を helper thread と並行させるかに関係します（先頭が `0` なら無効）。これらは `STRATA_VERIFY_STEPPED` 自体の有効判定ではありません。

## 実行時の詳細

通常の doorbell 経路では、`capture()` が token window を graph segment 群として記録します。各 layer group の doorbell publish 後に serve boundary が挿入され、既定では GPU plan copy と VRAM expert group の後にも split boundary が入ります。実行時は segment を順に投入し、serve boundary で queue drain 後に CPU pool callback を呼び、必要な plan/flag を公開してから後続 segment を進めます。split boundary では plan を公開できた時点で次 segment を投入し、CPU row 計算と重ねます。

全 expert 常駐経路では segment capture を行わず、必要な PLE rows を用意した後に `h_flag_` を 1 にして graph を実行します。いずれも `g_stepped` が有効なら通常の window 後の layer ごとのホスト待ち処理はスキップされます。

この設定は window 用 host memory の選択にも影響します。stepped 有効時は既定で `window_host_uncached()` が false となり、mapped buffer に `sycl::malloc_host` を使い、doorbell payload の plain store を選びます。`STRATA_VERIFY_HOST_UNCACHED` が `env_on()` 判定で有効なら uncached host allocation を維持します。この値も static cache されます。なおこのメモリ選択は `g_stepped` に基づくため、`STRATA_VERIFY_EAGER` などで segmented 実行に入らない場合にも適用されます。

通常は有効化を知らせる専用ログはありません。`STRATA_VERIFY_NODES` が設定されている場合（空文字を含む）は capture 時に segment 数を stderr に出します。実行失敗時は上記 remote-opt エラーのほか、queue drain 後の ring 不達で `verify (stepped): layer ... did not ring after its queue drained ...`、segment 処理中の例外で `verify (stepped): ...` などを `err` に設定します。

根拠: `sycl/src/core/verify.cpp:218-241, 1287-1297, 1361-1366, 1461-1466, 1687-1727, 1734-1738, 2041-2059, 2063-2149, 2180-2202`。

## 根拠

- 環境変数の値判定と起動時 cache: `sycl/src/core/verify.cpp:92-103`。
- host uncached allocation との相互作用: `sycl/src/core/verify.cpp:218-241`。
- lean path と shared-expert fork の抑止: `sycl/src/core/verify.cpp:803-810, 1287-1297`。
- segment hook と `STRATA_VERIFY_SPLIT` の判定: `sycl/src/core/verify.cpp:1687-1727`。
- segmented capture の選択: `sycl/src/core/verify.cpp:1734-1738`。
- stepped 実行分岐、remote expert-opt エラー、CPU serve と flag 公開: `sycl/src/core/verify.cpp:2041-2149`。
- all-resident 経路と stepped 後の通常 wait の抑止: `sycl/src/core/verify.cpp:2180-2202`。
- `docs/DETAILS.md` には `STRATA_VERIFY_STEPPED` の説明を確認できませんでした。性能値は本調査文書には記載していません。
