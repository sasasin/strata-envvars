# `STRATA_REFILL_SERIAL`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

serve のプロンプト処理で、プロンプト用に一時貸し出しした expert-cache slot を返却するとき、複数 GPU stage の refill を stage ごとに完了させるか、全 stage のコピーを先に発行してから待つかを切り替えます。通常の設定では、各 stage のコピーをすべてキューに入れてから、それぞれの完了を待ちます。変数が設定されていると、1 stage 分のコピーを発行して完了を待ち、次の stage に進みます。

読み取りは CUDA/HIP 系の `src/program/generate.cpp` と SYCL 版の `sycl/src/program/generate.cpp` に各1箇所あります。両方とも同じ判定・分岐です。プロンプト用 slot の貸し出しがない場合や、refill 対象の stage が1つ以下の場合は、設定の有無で処理順序は変わりません。

## 値と判定

値を parse せず、`getenv("STRATA_REFILL_SERIAL") != nullptr` だけを見ます。

| 状態 | 動作 |
|---|---|
| 未設定 | 複数 stage に refill がある場合、全 stage のコピー発行後に各 stage を待つ |
| 設定あり | 複数 stage に refill がある場合、stage ごとにコピー発行と完了待ちを行う |

`1` 以外の値でも、空文字でも、環境変数が存在すれば逐次方式になります。値の大文字小文字、数値形式、範囲は検査されません。CLI 引数や設定ファイルによる上書きはありません。

判定結果は関数内の `static const bool` に保存されます。宣言箇所の実行に初めて到達した際に読み取られ、その後プロセス内で環境を書き換えても再評価されません。

## 有効になる条件

- serve のプロンプト経路で、expert-cache の slot をプロンプト用バッファとして貸し出し、後で expert データを戻す処理に入ること。
- refill 時点で `p.lent` が空でない `PfPart` が2つ以上あること。`PfPart` は CUDA0 と layer split の各 stage のキャッシュを表します。実際に複数 `PfPart` に貸出中 slot がある場合にだけ、並列方式と逐次方式の分岐が異なります。
- layer split の各 stage が自分の cache/device にコピーを戻します。コピー先 slot と residency table を復元してから、各 device の residency table を再 upload します。

1 GPU の場合、または layer split でも貸出中 slot のある stage が1つだけの場合は、`refill_one()` が使われ、変数による差はありません。slot を貸し出していない構成でも refill 対象がなく、処理は変わりません。

## 実行時の詳細

各 stage の `refill_issue()` は、貸し出された expert blob を元の cache slot に戻し、host 側の residency 表を元に戻します。既定方式ではまず全 stage の `refill_issue()` を呼んでから、全 stage の `refill_wait()` で queued copy を同期します。`STRATA_REFILL_SERIAL` が設定されている場合は、stage ごとに `refill_issue()` の後すぐ `refill_wait()` を実行します。いずれも完了後に residency table を全 device へ upload します。これはコピーのスケジュールを変える設定で、refill する expert や slot の選択を変える処理ではありません。

`STRATA_REFILL_BLOCKING` も設定されていると、`refill_issue()` 内で各 slot の `fill_slot_blocking()` が使われます。この場合は各コピーがその場で待たれるため、複数 stage の「全コピー発行後に待つ」という既定方式もコピーの完了を先に待ちます。`STRATA_REFILL_SERIAL` の分岐自体は残りますが、非同期コピーを stage 間で重ねる差は生じません。

通常の refill は専用ログを出しません。`STRATA_TRACE` が設定されており、refill 対象があれば `strata trace: refilled <slot数> slots on <stage数> stage(s) in <時間> ms` を stderr に出します。refill に失敗した場合、呼び出し側は `ERR refilling a lent slot failed: ...` を stdout に出して要求処理を終了します。

## 文書・測定との照合

`docs/DETAILS.md` は prompt path が cache slot を借りて使い、refill 後に戻す構成を説明していますが、`STRATA_REFILL_SERIAL` 自体の既定値・挙動や性能測定は記載していません（同ファイル 206-213 行）。コードコメントには、逐次方式が旧 0.1.30/0.1.31 の stage ごとの処理であるとありますが、これはコメント上の説明として扱い、現在の動作根拠は以下の実装分岐とします。性能差はこの調査では測定していません。

## 根拠

- 値の読み取り、複数 stage の判定、既定の一括発行・待機と設定時の stage ごとの発行・待機: `src/program/generate.cpp:10831-10893`, `sycl/src/program/generate.cpp:10075-10139`。
- `PfPart` が CUDA0 と各 stage の cache/device/layer 範囲を保持すること、および貸出対象の組み立て: `src/program/generate.cpp:6517-6538,6576-6583`。
- 借りた slot の返却・refill 呼び出し、および refill 失敗時の結果: `src/program/generate.cpp:11190-11191,11240-11241`, `sycl/src/program/generate.cpp:10363-10369,10411-10415`。
- `STRATA_REFILL_BLOCKING` が slot ごとの blocking fill を選ぶこと: `src/program/generate.cpp:244-247,10838-10849`, `sycl/src/program/generate.cpp:286-289,10082-10095`。
- trace の出力: `src/program/generate.cpp:10886-10891`, `sycl/src/program/generate.cpp:10132-10137`。
- prompt slot の貸し出しと refill 後に戻す設計の記載: `docs/DETAILS.md:206-213`。
