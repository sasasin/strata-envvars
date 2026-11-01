# `STRATA_PARK_ASYNC`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の状態は `## main...origin/main` で、未コミット変更はありません。外部ライブラリの環境変数動作は対象外です。

## 役割

CUDA の会話キャッシュが会話を park するとき、K/V の退避を同期コピーから非同期コピーに切り替える opt-in です。K/V を GPU 上の段階バッファへコピーし、その後バックグラウンドスレッドが 4 MiB 単位で pinned host buffer に移して park 済み画像の host buffer を埋めます。park 後の次の処理と host へのコピーを重ねられる構造です。会話キャッシュを使わない通常の生成や、park が発生しないリクエストには作用しません。

## 値と判定

両方の読み取り箇所で `getenv()` の結果を一度だけ static cache し、文字列全体ではなく先頭 1 文字が `'1'` かを判定します。数値 parse、空白除去、大文字小文字変換はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効（設定済みだが `v[0]` は `\0`） |
| `1`, `10`, `1anything` | 有効 |
| `0`, `true`, ` 1`, その他先頭文字が `1` でない値 | 無効 |

CLI 引数による上書きはありません。`src/program/generate.cpp` と `src/core/conversation_snapshot.cpp` は別々に初回参照時の結果を cache します。実行中に環境値を変更しても、各 helper が一度評価された後は再評価されません。

根拠: `src/program/generate.cpp:305-308`, `src/core/conversation_snapshot.cpp:231-237`。

## 有効になる条件

- `strata serve` の会話キャッシュが有効で、park 対象となる非空の live conversation があること。serve の切り替え・復帰経路で park が必要になったときに `park_current()` が呼ばれます。会話キャッシュが無効、live state が空、または park を省く経路では K/V コピー処理に入りません。`--conversation-cache-min-tokens` 等による park skip や cache budget / RAM admission の拒否も別途あります。
- K/V の非同期 stage は CUDA 実装でのみ有効です。`STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` の build では `park_async_on()` が常に false を返します。ただし HIP では `generate.cpp` 側の `park_async_env()` に backend guard がないため、単一段の main conversation を park する条件では、この値が K/V を非同期化せずに checkpoint の選別・移動を変えることがあります。SYCL 実装にはこの名前の環境読み取りがなく、`sycl/src/core/conversation_state.cpp` の snapshot 保存は同期経路です。
- stage を確保するには、CUDA device を取得でき、2 個の 4 MiB pinned host buffer と stream の初期化が成功し、stage 用の丸め済み VRAM 容量に加えて 1.5 GiB 以上の空きがある必要があります。`STRATA_PARK_VRAM_MIB` が設定され、slot を確保できる場合は通常の stage の代わりに slot が使われます。
- `STRATA_PARK_ASYNC` が有効で、単一段（layer split なし）の main conversation を park すると、park 対象外の checkpoint を park 画像へ移す選別も行われます。全 checkpoint を移すかどうかは incoming conversation / borrow / batch slot / cvec 変更などで決まります。これは K/V stage の可否とは別の処理です。

根拠: `src/program/generate.cpp:10554-10576,10707-10720,10754-10761,14391-14403`; `src/core/conversation_snapshot.cpp:231-237,595-659`; `sycl/src/core/conversation_state.cpp:258-285`。

## 実行時の詳細

serve 側では park 前に必要 K/V 容量を見積もり、`conversation_park_async_begin()` を呼んで stage を準備します。利用可能なら各 K/V 層の device-to-device コピーを stage に記録し、park capture 完了時に stream を同期してコピーの到着を確認してから、バックグラウンドスレッドを起動します。そのスレッドは二つの pinned buffer を交互に使って stage から host buffer へコピーします。park 画像には pending token が付き、画像を解放するときや K/V 読み取り側が必要なときに `conversation_park_join()` がコピーを待ちます。`STRATA_PARK_VRAM_MIB` の VRAM slot を使った場合は K/V 層にも pending token が付きます。

未設定・無効値のほか、CUDA device 取得、stream / pinned buffer 初期化、VRAM 条件、stage allocation のいずれかが満たされない場合は `begin()` が false を返し、その park の K/V は `conversation_kv_save()` の通常の同期 `transfer()` 経路で保存されます。これらの初期化失敗はこの箇所では警告されず、同期コピーへの fallback です。stage への非同期 device copy または launch 時の同期に失敗すると snapshot 保存は失敗し、serve の park 呼び出し元は `ERR ...` を stdout に出して終了コード 1 を返す経路があります。一方、バックグラウンド host copy の完了エラーは stderr に `strata: STRATA_PARK_ASYNC: a parked K/V copy failed (%s)` と出ますが、`conversation_park_join()` 自体はエラーを返さず、serve の終了には結び付けません。

park の通常ログは `strata serve: conversation cache: parked ... in ... ms` で、変数名や async の有効化を直接示すログではありません。`STRATA_PARK_TRACE` が設定されると `strata parktrace: ...` の timing log が stderr に出ます。

根拠: `src/core/conversation_state.cpp:571-617`; `src/core/conversation_snapshot.cpp:292-379,581-588,595-659,673-725`; `src/program/generate.cpp:10717-10721,10741-10750,14404-14429`。

## 資料の記載と測定値

`docs/DETAILS.md:1504-1518` は本機能を CUDA opt-in とし、HIP / gfx906 / Metal では無効と説明しています。コードでも K/V 非同期 stage はこれらの backend で無効です。一方、HIP では上記の checkpoint 選別・移動が環境値で有効になり得るため、「変数が一切作用しない」という意味ではコードと一致しません。表にある park 時間（3.3K / 13K token の会話で 212-217 / 329-334 ms から 64-75 / 68 ms）は変更作者が CMP 170HX（GA100、sm_80）、PCIe Gen2 x4 で報告した測定値です。同じ節に一部の park 値は別の opt-in switch も設定したとあり、Strata 側で再測定した結果ではありません。一般的な速度向上としては扱えません。

## 根拠

- 値の読み取りと cache: `src/program/generate.cpp:305-308`, `src/core/conversation_snapshot.cpp:231-237`。
- serve の park 条件、checkpoint 移動、snapshot 保存: `src/program/generate.cpp:10554-10576,10707-10720,10754-10761,14391-14429`。
- K/V の staging、同期 fallback、background copy、待ち合わせと失敗ログ: `include/strata/core/conversation_snapshot.hpp:80-92`, `src/core/conversation_snapshot.cpp:351-379,581-588,595-659,673-725`。
- CUDA / HIP compile 条件: `src/core/conversation_snapshot.cpp:231-237`, `cmake/hip_backend.cmake:94-98`。SYCL の同期保存箇所: `sycl/src/core/conversation_state.cpp:258-285`。
- docs の説明と測定条件: `docs/DETAILS.md:1504-1518`。
