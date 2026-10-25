# `STRATA_VERIFY_STEPPED`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

SYCL backend の検証 window を layer ごとの graph segment に分け、各 segment の境界で CPU expert pool を実行する stepped mode を有効にします。通常の doorbell window では GPU graph が走っている間に CPU と GPU がホスト共有フラグを読み書きします。stepped mode は、ホスト側のフラグを立ててから後続 segment を投入し、segment 完了後に GPU のリングと payload を読む順序にします。これは環境変数を読む `sycl/src/core/verify.cpp` の検証実装に限られ、CUDA/HIP 実装にはこの変数の読み取りがありません。

## 値と判定

`env_on()` は環境変数の文字列全体を parse せず、未設定・空文字・先頭文字 `0` を false、それ以外を true とします。空白除去、大文字小文字変換、数値変換はありません。

| 値 | 判定 |
|---|---|
| unset | OFF |
| 空文字 | OFF |
| `0`, `0anything` | OFF |
| `1`, `10`, `true`, `false`, `anything`, ` 0` | ON |

判定結果 `g_stepped` は翻訳単位スコープの `const bool` として初期化されるため、プロセス起動時に一度だけ読み取られます。起動後の環境変更では切り替わりません。根拠: `sycl/src/core/verify.cpp:93-104`。

## 有効になる条件

- SYCL backend の検証 window を実行する経路でのみ参照されます。
- 通常の doorbell graph では、`STRATA_VERIFY_EAGER` が未設定で segment capture が成功した場合に stepped run になります。`STRATA_VERIFY_EAGER` が設定されていると、非 resident window は eager replay に戻ります。
- all-resident graph では通常の layer serve がないため、stepped run ではなく、launch 前に PLE の準備と window flag の設定を済ませます。最終的な host wait を省略する分岐もこの stepped 状態に従います。
- all-resident 経路で `STRATA_VERIFY_EAGER` が設定されていても `stepped_ar` の判定からは除外されません。eager replay に先立つ flag 設定と stepped 用の後段処理スキップは残ります。
- stepped run で `--remote-expert-opt` が有効なら window は失敗し、`verify: STRATA_VERIFY_STEPPED does not serve --remote-expert-opt` を返します。
- segment の split point は `STRATA_VERIFY_SPLIT` で調整されます（未設定・空文字・先頭が `0` 以外なら ON）。`STRATA_VERIFY_PIPE` は split point の次の segment と CPU pool 実行を重ねるかを制御し、値が未設定・空文字・先頭が `0` 以外なら ON です。`STRATA_VERIFY_NODES` は値を問わず設定されている場合に capture した segment 数を stderr に出します。これらは別々の設定で、`STRATA_VERIFY_STEPPED` を ON にしただけでは split point や pipelining が必ず使われるとは限りません。

## 実行時の詳細

非 resident window では `capture()` が graph body を記録し、`step_hook_` が doorbell publish の serve point ごとに graph を閉じて次の segment を開始します。split が有効なら VRAM expert groups の後にも境界を作ります。実行時は segment を投入し、serve point で queue の完了と GPU ring を確認してから CPU pool を呼び、plan copy 完了後に flag B と次の window flag を立てます。CPU pool の plan 公開後に次 segment を投入する pipelined serve は `STRATA_VERIFY_PIPE` に依存します。根拠: `sycl/src/core/verify.cpp:1705-1745,1752-1755,2065-2175`、doorbell publish 後の hook は `sycl/src/core/verify.cpp:1343-1374`。

all-resident window では GPU 側が residency table から plan を作るため layer ごとの serve はありません。stepped mode は必要な PLE rows を用意し、launch 前に `h_flag_` を立てます。window 後の通常の per-layer ring wait と CPU pool serve は `stepped_run || stepped_ar` の場合にスキップされます。根拠: `sycl/src/core/verify.cpp:2065-2079,2212-2226`。

このモードでは window buffer を通常の host USM として確保し、doorbell payload の publish も uncached payload store を使わない設定になります。`STRATA_VERIFY_HOST_UNCACHED` が `env_on()` 判定で ON の場合はこの変更を抑え、従来の uncached host memory/store を使います。根拠: `sycl/src/core/verify.cpp:219-242`。

stepped mode 中は共有 expert stream の fork も選択されません。また、device-plan の lean 経路も `g_stepped` が ON なら使われません。根拠: `sycl/src/core/verify.cpp:817,1301-1305`。

## 根拠

- 値の判定と一度だけ行う読み取り: `sycl/src/core/verify.cpp:93-104`。
- window の buffer 属性と `STRATA_VERIFY_HOST_UNCACHED` の相互作用: `sycl/src/core/verify.cpp:219-242`。
- graph segment の capture、split hook、segment 数ログ: `sycl/src/core/verify.cpp:1705-1745,1752-1755`。
- stepped / all-resident window の実行条件と remote expert のエラー: `sycl/src/core/verify.cpp:2065-2084,2212-2226`。
- mode の設計理由とコメント中の A770 測定記録: `sycl/src/core/verify.cpp:219-224`。測定記録は実装コメント内の記載として扱い、この調査で再計測した値ではありません。`docs/DETAILS.md` と `docs/INTEL.md` にはこの環境変数を個別に説明する記述は見つかりませんでした。
