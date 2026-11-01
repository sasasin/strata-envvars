# `STRATA_PARK_VRAM_MIB`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

会話を park するとき、保存する K/V のコピーを通常のホスト側バッファに加えて CUDA VRAM にも残すための MiB 予算です。park 後に同じ会話を復元するとき、該当する K/V が slot に残っていれば VRAM から VRAM へコピーします。通常のホストバッファへの保存も続くため、slot が使えない場合や解放された場合はそちらから復元できます。

この機能は `STRATA_PARK_ASYNC` が有効な park に付加されます。`STRATA_PARK_ASYNC` が無効なら VRAM slot は作られません。予算値の取得は slot の取得経路のほか、VRAM 解放 helper と `STRATA_PARK_TRACE` 有効時の復元 trace からも呼ばれるため、まれに slot を作らない経路で環境値だけ読むことがあります。実装の非同期 park は HIP、gfx906 互換、Metal ではコンパイル時に無効です。

## 値と判定

値は `std::atoll` で先頭から整数へ変換されます。変換結果が正数なら MiB 単位の予算として `size_t` に変換し、20 bit 左シフトして bytes にします。0 以下なら予算 0、すなわち slot 無効です。文字列全体の検査や追加の clamp はありません。

| 値 | 判定 |
|---|---|
| unset | 0 MiB、無効 |
| 空文字、数字で始まらない文字列 | `atoll` が 0 を返すため無効 |
| `0`、負数 | 0 以下のため無効 |
| 正の整数 | その MiB 数を予算にする。先頭の空白や符号は `atoll` の変換に従い、整数の後ろの文字列は検査されない（例: `64tail` は 64） |

数値の後ろに単位を書く形式には対応しません。`atoll` の整数変換範囲外となる値について、実装はエラー検査や fallback を定義していません。変換結果が正でも slot の確保が保証されるわけではありません。

既定値は 0 MiB です。CLI 引数や設定ファイルによる上書きはこの読み取り経路にはなく、他の変数との優先順位もありません。`STRATA_PARK_ASYNC` は slot 機能の前提条件です。

根拠: `src/core/conversation_snapshot.cpp:137-144,159-182,231-237,595-617`。

## 有効になる条件

slot の取得には次の条件が必要です。

- ビルドが `STRATA_USE_HIP`、`STRATA_HIP_GFX906`、`STRATA_GPU_METAL` のいずれでもなく、CUDA 系の実装経路を通る。
- `STRATA_PARK_ASYNC` が設定され、その先頭文字が `1`。値全体は検査されないため `1anything` も有効、空文字や `true` は無効。
- park する K/V の必要 byte 数が 0 ではない。
- 対象 device の slot について予算内の容量が確保でき、必要に応じて新規確保時に VRAM 条件も満たす。

環境変数値から得た予算内に slot 容量を収めます。新規 slot の容量は必要量を 64 MiB 単位に切り上げます。容量の合計が予算を超える場合はその取得を断ります。さらに新規割り当てでは、必要容量に加えて 1.5 GiB の空き VRAM を要求します。既存の十分な空き slot を再利用する場合は、この新規割り当て時の空き VRAM 検査を通りません。

予算が 0、予算超過、空き VRAM 不足、`cudaMalloc` 失敗のいずれかで slot が取れないと、非同期 park 自体が有効なら通常の非同期 stage を試します。stage も使えない場合は K/V を同期コピーします。したがって、この変数は park を必ず成功させる設定ではなく、同期コピーを禁止する設定でもありません。

根拠: `src/core/conversation_snapshot.cpp:159-190,231-237,595-659`。

## 実行時の詳細

`park_vram_budget()` は初回呼び出し時に `getenv` と変換を行い、その結果を関数内 `static const size_t` に保存します。呼び出しは非同期 park の slot 選択、VRAM 解放 helper、`STRATA_PARK_TRACE` 有効時の restore trace にあります。最初にどの経路が呼ぶかで cache が初期化され、その後プロセス環境が変わっても予算は再評価されません。`STRATA_PARK_ASYNC` 自体も関連する各関数内の static 値として読み取られます。

park の開始時、Strata は同じ device の空き slot のうち必要量以上で最小のものを再利用します。該当する slot がなければ、未使用 slot を解放してから容量予算と空き VRAM を確認し、新しい slot を確保します。slot を取った場合、各 K/V 部分を device-to-device copy で slot に写し、通常の保存バッファにも背景コピー用の項目を記録します。slot の容量に収まらない部分や device memory と判定されない部分は同期転送します。保存完了後、背景コピーが slot を読み終えるまで slot を保持します。

restore は画像の tag に対応する slot に必要な各部分が揃っていれば slot から K/V を転送し、揃わない場合は背景コピーを join して通常のホストバッファから復元します。prefix restore も同様に slot を利用します。slot は画像または K/V 層の保持 token が解放されると再利用可能になり、K/V の拡張で再割当てが必要になった場合には park 済み slot をまとめて解放して再試行します。

予算が正で `STRATA_PARK_TRACE` が設定されていると、stderr の `strata parktrace:` に slot の取得容量と tag、または取得できなかった理由（`budget`、`vram`、`cudaMalloc` など）が出ます。予算が 0 のときは slot の理由ログを出しません。K/V の背景コピー失敗時には join で `strata: STRATA_PARK_ASYNC: a parked K/V copy failed (...)` が stderr に出ます。slot copy 自体のエラーは snapshot のエラーとして返り、呼び出し元の会話キャッシュ処理が park を見送る経路があります。slot 取得失敗だけでは警告や終了にならず、上記の stage / 同期経路に移ります。

`docs/DETAILS.md` は、作者による CMP 170HX 測定として2回目以降の restore が 33–51 ms から 7–13 ms になったと記載し、初回は速くならなかったとしています。同じ節は測定が変更作者によるもので、Strata 作者側には sm_80 カードがなく独自測定していないと明記しています。この値はその記載条件の報告値です。

根拠: `src/core/conversation_snapshot.cpp:137-190,292-349,455-506,581-617,662-759`; `src/core/conversation_state.cpp:551-619,696-708`; `src/program/generate.cpp:8917-8922`; `docs/DETAILS.md:1504-1518`。

## 根拠

- 読み取りと byte 予算化: `src/core/conversation_snapshot.cpp:137-144`。
- 予算判定、slot の再利用・新規確保、境界条件: `src/core/conversation_snapshot.cpp:159-190`。
- 非同期機能の backend 条件と `STRATA_PARK_ASYNC` 判定: `src/core/conversation_snapshot.cpp:231-237`。
- snapshot 保存・復元時の slot copy と fallback: `src/core/conversation_snapshot.cpp:292-349,455-506`。
- park の開始・slot 取得失敗時の stage fallback: `src/core/conversation_snapshot.cpp:595-659`。
- 非同期 copy の失敗ログ、slot の解放: `src/core/conversation_snapshot.cpp:581-588,662-759`。
- serve loop の K/V 拡張時に slot を解放して再試行: `src/program/generate.cpp:8917-8922`。
- 文書に記載された測定の範囲: `docs/DETAILS.md:1504-1518`。
